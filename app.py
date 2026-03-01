import warnings

# Suppress the specific future warning for clean_up_tokenization_spaces
warnings.filterwarnings("ignore", message=".*clean_up_tokenization_spaces.*")

from flask import Flask, jsonify, render_template, request, redirect, url_for
import psycopg2
from sentence_transformers import SentenceTransformer
from groq import Groq
from dotenv import load_dotenv
import os
from FlagEmbedding import FlagReranker
import re

app = Flask(__name__)

os.environ['HF_HOME'] = './model_cache'
os.environ['TRANSFORMERS_CACHE'] = './model_cache'
os.environ['SENTENCE_TRANSFORMERS_HOME'] = './model_cache'


# Load environment variables from .env file
load_dotenv()

# Access variables
api_key = os.getenv('API_KEY')
db_user = os.getenv('DB_USER')
db_host = os.getenv('DB_HOST')
db_password = os.getenv('DB_PASSWORD')
db_name = os.getenv('DB_NAME') 

# Initialize SBERT for embedding generation without torch
sbert_model = SentenceTransformer('all-MiniLM-L6-v2')  # Ensure 'cpu' if torch isn't used

# Connect to PostgreSQL Database
def get_db_connection():
    return psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )

# Convert query to embedding and search for the top-15 most similar text.
def search_similar_texts(user_query,  table_name, top_n=15):
    
    # Generate the embedding for the user query
    query_embedding = sbert_model.encode(user_query).tolist()
    
    # Connect to the database
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Use pgvector to find the most similar text based on cosine similarity
    query= f"""
        SELECT source, text, embedding <#> %s::vector AS similarity
        FROM {table_name}
        ORDER BY similarity
        LIMIT %s;
    """
    cursor.execute(query, (query_embedding, top_n))
    
    # Fetch the results
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

reranker = FlagReranker('BAAI/bge-reranker-base', use_fp16=True)  # Smaller, faster model
# Reranking of top 15 results to get top 5 results 
def get_final_results(query):
    results= search_similar_texts(query, "aiml_dataset")
    # Make a dictionary to get the relevance score given by model as value and index of the doc as key.
    results_with_scores = {}
    
    for i, result in enumerate(results):
        score = reranker.compute_score([query, result[1]])
        results_with_scores[i] = score[0]
        
    # Sort the dictionary by value in descending order and get the top 5 keys
    top_5_keys = [key for key, value in sorted(results_with_scores.items(), key=lambda item: item[1], reverse=True)[:5]]
    
    # Get combined data from the results corresponding to top 7 keys.
    provided_context = ""
    for x in top_5_keys:
        print(results[x][1])
        provided_context = provided_context+"\n"+ results[x][1]
    return provided_context

# Using groq API key to use Llama model.

client = Groq(
    api_key= api_key
)

def final_response(user_query):
    context_info = get_final_results(user_query)
    # Generating summarized responses from the context.
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": """You are an AI assistant. Use only the provided context to answer the user's query. 
            Your response should be in a clear and readable format, like bullet points or short paragraphs or heading wise whenever needed. 
            Do not add any additional information outside the context provided. 
            If there are multiple pieces of context, break them down logically. 
            Do not include any indication in the response that the answer comes from context.
            If the user's query has minor typos or spelling mistakes, try to match it with similar terms in the context.
            Only respond with 'Couldn't find the answer' if the context is completely unrelated to the query."""},
            {"role": "assistant", "content": f"The following context will guide my response: {context_info}"},
            {"role": "user", "content": user_query,}
        ],
        model="llama-3.3-70b-versatile",
    )
    return chat_completion.choices[0].message.content

# Code to format answers - convert markdown and newlines to HTML
@app.template_filter('format_answer')
def format_answer(answer):
    # Convert markdown bold (**text**) to HTML <strong> - do this FIRST
    answer = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', answer)
    
    # Convert bullet points (* text) to HTML list items
    # Match lines that start with * followed by space
    answer = re.sub(r'^\* (.+)$', r'• \1', answer, flags=re.MULTILINE)
    
    # Convert newlines to <br>
    answer = answer.replace('\n', '<br>')
    
    return answer

# Code to format query in title case
@app.template_filter('format_query')
def format_query(query):
    # Convert to title case (capitalize first letter of each word)
    return query.title()

@app.route("/", methods=["GET", "POST"])
def query_form():
    # Load recent history from DB
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, query, answer FROM user_feedback ORDER BY id DESC LIMIT 20")
    history = [{"_id": row[0], "query": row[1], "answer": row[2]} for row in cursor.fetchall()]
    cursor.close()
    conn.close()

    if request.method == "POST":
        query = request.form.get("query")
        if query:
            # Generate an answer
            answer = final_response(query)
            print("Final answer\n", answer)
            # Insert query-answer pair into PostgreSQL
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO user_feedback (query, answer)
                VALUES (%s, %s) RETURNING id;
                """,
                (query, answer)
            )
            inserted_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for("query_form"))  # Redirect to clear POST data
    return render_template("index.html", history=history)

@app.route("/feedback/<int:response_id>/<feedback_type>", methods=["POST"])
def submit_feedback(response_id, feedback_type):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE user_feedback
        SET feedback = %s
        WHERE id = %s;
        """,
        (feedback_type, response_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return jsonify({"message": "Feedback submitted successfully!"}), 200

if __name__ == "__main__":
    app.run(debug=True)


#                 List of relations
#  Schema |         Name         | Type  |  Owner   
# --------+----------------------+-------+----------
#  public | aiml_dataset         | table | postgres
#  public | chatbot_interactions | table | postgres
#  public | question_frequency   | table | postgres
#  public | user_feedback        | table | postgres
# (4 rows)
