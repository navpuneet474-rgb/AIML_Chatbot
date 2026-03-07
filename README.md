# AI/ML Chatbot - RAG-based Question Answering System

A Retrieval-Augmented Generation (RAG) chatbot that answers AI/ML questions using semantic search, reranking, and large language models. Built with Flask, PostgreSQL, and Groq API.

## Features

- **Semantic Search**: Uses sentence embeddings to find contextually relevant information
- **Two-Stage Retrieval**: Fast initial retrieval followed by precise reranking for optimal accuracy
- **Grounded Responses**: LLM answers are constrained to retrieved context to prevent hallucinations
- **Answer Caching**: Automatically caches answers for identical queries to improve response time
- **Question Frequency Tracking**: Monitors how often each question is asked with timestamps
- **Trending Questions**: Displays top 5 most frequently asked questions in the sidebar
- **Query Normalization**: Cleans and normalizes user queries for better matching
- **Typo Tolerance**: Handles minor spelling mistakes (e.g., "KL-Diversion" → "KL-Divergence")
- **Smart Fallback Messages**: Helpful guidance when a question is outside the knowledge base
- **User Feedback System**: Thumbs up/down mechanism to measure response quality
- **Chat History**: Displays last 20 query-answer pairs with feedback options
- **Clean UI**: Responsive web interface with formatted answers (bold text, bullet points)

## Tech Stack

- **Backend**: Flask (Python 3.10+)
- **Database**: PostgreSQL with pgvector extension
- **Embedding Model**: SentenceTransformer (all-MiniLM-L6-v2)
- **Reranker**: FlagEmbedding (BAAI/bge-reranker-base)
- **LLM**: Llama 3.3 70B via Groq API
- **Frontend**: HTML, CSS, JavaScript

## Architecture

### Pipeline Flow

```
User Query
    ↓
Check Answer Cache (PostgreSQL)
    ↓ (if cache miss)
Query Normalization (Regex cleaning)
    ↓
Query Embedding (SentenceTransformer)
    ↓
Vector Search → Top 15 Results (PostgreSQL + pgvector)
    ↓
Reranking → Top 5 Results (FlagEmbedding)
    ↓
Context + Query → LLM (Llama 3.3 70B)
    ↓
Generated Answer
    ↓
Store in Database + Track Question Frequency
```

### Why RAG?

Unlike traditional chatbots that rely solely on pre-trained knowledge:

- **Dynamic Knowledge**: Update the database without retraining the model
- **Reduced Hallucinations**: Responses are grounded in retrieved facts
- **Domain-Specific**: Specialized for AI/ML topics with curated knowledge base

## Installation

### Prerequisites

- Python 3.10 or higher
- PostgreSQL 12+ with pgvector extension
- Groq API key

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <project-directory>
```

### 2. Set Up Virtual Environment

```bash
python -m venv AIML_CHATBOAT
source AIML_CHATBOAT/bin/activate  # On Windows: AIML_CHATBOAT\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Up PostgreSQL Database

Install required extensions:

```sql
CREATE EXTENSION vector;
CREATE EXTENSION pg_trgm;
```

Create required tables:

```sql
-- Main knowledge base
CREATE TABLE aiml_dataset (
    id SERIAL PRIMARY KEY,
    source TEXT,
    text TEXT NOT NULL UNIQUE,
    embedding vector(384) NOT NULL
);

-- User query history and feedback
CREATE TABLE user_feedback (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    answer TEXT NOT NULL,
    feedback INTEGER,
    text_feedback TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Question frequency tracking
CREATE TABLE question_frequency (
    question TEXT PRIMARY KEY,
    frequency INTEGER DEFAULT 1,
    last_asked TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Create indexes for faster search:

```sql
-- Vector similarity search
CREATE INDEX ON aiml_dataset USING ivfflat (embedding vector_cosine_ops);

-- Fuzzy text search
CREATE INDEX text_gin_trgm_idx ON aiml_dataset USING gin (text gin_trgm_ops);
```

### 5. Configure Environment Variables

Create a `.env` file in the project root:

```env
API_KEY=your_groq_api_key_here
DB_USER=your_postgres_username
DB_HOST=localhost
DB_PASSWORD=your_postgres_password
DB_NAME=your_database_name
```

### 6. Populate the Database

Load your AI/ML documents into the `aiml_dataset` table with embeddings:

```python
from sentence_transformers import SentenceTransformer
import psycopg2

model = SentenceTransformer('all-MiniLM-L6-v2')

documents = [
    {"source": "ML Basics", "text": "Machine learning is..."},
    # Add more documents
]

conn = psycopg2.connect(...)
cursor = conn.cursor()

for doc in documents:
    embedding = model.encode(doc["text"]).tolist()
    cursor.execute(
        "INSERT INTO aiml_dataset (source, text, embedding) VALUES (%s, %s, %s)",
        (doc["source"], doc["text"], embedding)
    )

conn.commit()
```

## Usage

### Run the Application

```bash
python app.py
```

The application will be available at `http://localhost:5000`

### Using the Chatbot

1. **Ask a Question**: Enter your AI/ML question in the text box
2. **Submit**: Click "Ask" or press Enter
3. **View Answer**: See the formatted answer in the chat history
4. **Provide Feedback**: Use thumbs up/down buttons to rate the response
5. **Browse History**: Scroll through the last 20 questions and answers
6. **Try Trending**: Click on trending questions in the sidebar to instantly ask them

## Project Structure

```
.
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create this)
├── .gitignore              # Git ignore file
├── templates/
│   └── index.html          # Main web interface
├── static/
│   ├── css/
│   │   └── styles.css      # Styling
│   └── js/
│       └── script.js       # Frontend JavaScript
└── model_cache/            # Cached ML models (auto-created)
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Main chat interface |
| POST | `/` | Submit a new query |
| POST | `/feedback/<id>/<type>` | Submit thumbs up (1) or down (0) |

## Performance Optimizations

- **Answer Caching**: Returns cached answers instantly for repeated questions, reducing API costs
- **FP16 Precision**: Reranker uses half-precision for 2x speed improvement
- **Vector Indexing**: IVFFlat index for fast approximate nearest neighbor search
- **Model Caching**: ML models cached locally in `./model_cache`
- **Query Normalization**: Strips special characters for better cache hits and embedding quality
- **Two-Stage Retrieval**: Fast initial filter (Top-15) reduces reranker workload before final Top-5 selection

## Troubleshooting

### Models Not Downloading

```bash
export HF_HOME=./model_cache
export TRANSFORMERS_CACHE=./model_cache
```

### Database Connection Issues

```bash
psql -U your_username -d your_database -h localhost
```

### Slow Response Times

- Verify database indexes are created
- Check Groq API key is valid and has quota remaining
- Consider reducing `top_n` in `search_similar_texts()`

### Clearing Bad Cached Answers

If incorrect answers were cached, clean them up with:

```sql
DELETE FROM user_feedback WHERE answer ILIKE '%couldn''t find the answer%';
```

## Future Improvements

- [ ] Implement hybrid search (vector + keyword)
- [ ] Add source citation in responses
- [ ] Add streaming responses for better UX
- [ ] Add monitoring dashboard for performance metrics

## License

This project is open source and available under the MIT License.

## Acknowledgments

- **SentenceTransformers** for embedding models
- **FlagEmbedding** for reranking capabilities
- **Groq** for fast LLM inference
- **pgvector** for PostgreSQL vector extension
