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
sbert_model = SentenceTransformer('all-MiniLM-L6-v2')

# Connect to PostgreSQL Database
def get_db_connection():
    return psycopg2.connect(
        host=db_host,
        database=db_name,
        user=db_user,
        password=db_password
    )

# Answer caching
def get_cached_answer(query):
    """Check if the exact same question was asked before and return cached answer."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT answer FROM user_feedback 
        WHERE LOWER(query) = LOWER(%s) 
        ORDER BY id DESC LIMIT 1
    """, (query,))
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    return result[0] if result else None

# question frequency tracking
def track_question(query):
    """Insert or increment frequency for a given query."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO question_frequency (question, frequency, last_asked)
        VALUES (%s, 1, CURRENT_TIMESTAMP)
        ON CONFLICT (question)
        DO UPDATE SET
            frequency = question_frequency.frequency + 1,
            last_asked = CURRENT_TIMESTAMP;
    """, (query,))
    conn.commit()
    cursor.close()
    conn.close()

# trending question
def get_trending_questions(limit=5):
    """Fetch the most frequently asked questions."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT question, frequency 
        FROM question_frequency 
        ORDER BY frequency DESC, last_asked DESC
        LIMIT %s
    """, (limit,))
    results = [{"question": row[0], "frequency": row[1]} for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return results


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

reranker = FlagReranker('BAAI/bge-reranker-base', use_fp16=True) 

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
    normalized_query = re.sub(r'[^a-zA-Z0-9 ]', ' ', user_query).strip()
    context_info = get_final_results(normalized_query)
    chat_completion = client.chat.completions.create(
        messages=[
            {"role": "system", "content": """You are an AI/ML specialized chatbot. Use only the provided context to answer the user's query. 
            Your response should be in a clear and readable format, like bullet points or short paragraphs or heading wise whenever needed. 
            Do not add any additional information outside the context provided. 
            If there are multiple pieces of context, break them down logically. 
            Do not include any indication in the response that the answer comes from context.
            If the user's query has minor typos or spelling mistakes, try your best to match it with the closest similar term in the context and answer based on that.
            For example, if the user writes 'KL-Diversion', treat it as 'KL-Divergence' if that exists in the context.
            
            If the context has absolutely no relation to the query:
            - If the question is about AI/ML topics but not in the knowledge base, respond: "I don't have information about this topic in my knowledge base. Please try asking about other AI/ML concepts."
            - If the question is completely outside AI/ML domain (like general knowledge, people, current events), respond: "I'm specialized in AI/ML topics only. Please ask questions related to Artificial Intelligence and Machine Learning."
            """},
            {"role": "assistant", "content": f"The following context will guide my response: {context_info}"},
            {"role": "user", "content": normalized_query}
        ],
        model="llama-3.3-70b-versatile",
    )
    return chat_completion.choices[0].message.content

# Format answer
@app.template_filter('format_answer')
def format_answer(answer):
    answer = re.sub(r"If you're looking for.*?couldn't find the answer.*?\.", "", answer, flags=re.IGNORECASE | re.DOTALL)
    answer = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', answer)
    answer = re.sub(r'^\* (.+)$', r'• \1', answer, flags=re.MULTILINE)
    answer = answer.replace('\n', '<br>')
    return answer

# Format query in title case
@app.template_filter('format_query')
def format_query(query):
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

    # Fetch trending questions for sidebar
    top_questions = get_trending_questions(limit=5)

    if request.method == "POST":
        query = request.form.get("query")
        if query:
            # Check cache first
            cached = get_cached_answer(query)
            if cached:
                print("Cache hit! Returning cached answer.")
                answer = cached
            else:
                print("Cache miss. Generating new answer...")
                answer = final_response(query)

            # Track question frequency
            track_question(query)

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
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for("query_form"))

    return render_template("index.html", history=history, top_questions=top_questions)


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
