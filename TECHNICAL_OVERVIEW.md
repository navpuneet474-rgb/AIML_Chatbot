# AI/ML Chatbot - Technical Overview

## Project Architecture

This is a **Retrieval-Augmented Generation (RAG)** chatbot built with Flask that answers AI/ML questions using a PostgreSQL vector database and LLM.

### Tech Stack

- **Backend**: Flask (Python web framework)
- **Database**: PostgreSQL with pgvector extension
- **Embedding Model**: SentenceTransformer (all-MiniLM-L6-v2)
- **Reranker**: FlagEmbedding (BAAI/bge-reranker-large)
- **LLM**: Llama3-70B via Groq API
- **Frontend**: HTML/CSS/JavaScript

---

## How It Works (Pipeline)

### 1. **Query Processing**

User submits a question → System converts it to embedding vector

### 2. **Semantic Search (Top-15 Retrieval)**

```python
query_embedding = sbert_model.encode(user_query).tolist()
```

- Converts query to 384-dimensional vector using SentenceTransformer
- Uses pgvector's cosine similarity (`<#>` operator) to find 15 most similar documents
- Returns: source, text, similarity score

### 3. **Reranking (Top-15 → Top-5)**

```python
reranker = FlagReranker('BAAI/bge-reranker-large', use_fp16=True)
score = reranker.compute_score([query, result[1]])
```

- Takes top-15 results and reranks them using a more sophisticated model
- Selects top-5 most relevant chunks
- Combines them into context string

### 4. **LLM Generation**

```python
chat_completion = client.chat.completions.create(
    messages=[
        {"role": "system", "content": "Use only provided context..."},
        {"role": "assistant", "content": f"Context: {context_info}"},
        {"role": "user", "content": user_query}
    ],
    model="llama3-70b-8192"
)
```

- Sends context + query to Llama3-70B
- LLM generates answer based ONLY on provided context
- Returns formatted response

### 5. **Feedback Collection**

- Stores query-answer pairs in PostgreSQL
- Users can provide thumbs up/down feedback
- Feedback stored for quality measurement

---

## Key Technical Concepts

### Why Embeddings?

**Embeddings convert text into numerical vectors that capture semantic meaning.**

**Benefits:**

1. **Semantic Search**: Finds conceptually similar content, not just keyword matches
   - Query: "neural networks" matches "deep learning architectures"
2. **Efficient Similarity**: Vector operations (cosine similarity) are fast
3. **Language Understanding**: Captures context and relationships between words

**Example:**

- "What is machine learning?" → [0.23, -0.45, 0.67, ...]
- "Explain ML concepts" → [0.21, -0.43, 0.69, ...] (similar vector!)

### RAG vs Normal LLM

| Aspect               | Normal LLM                  | RAG (This Project)          |
| -------------------- | --------------------------- | --------------------------- |
| **Knowledge Source** | Training data only (static) | External database (dynamic) |
| **Accuracy**         | May hallucinate             | Grounded in retrieved facts |
| **Updates**          | Requires retraining         | Update database anytime     |
| **Domain-Specific**  | Generic knowledge           | Specialized (AI/ML docs)    |
| **Citations**        | Cannot cite sources         | Can track source documents  |

**This Project's Advantage:**

- LLM has cutoff date, but your database can be updated daily
- Reduces hallucinations by constraining responses to retrieved context
- Can handle proprietary/domain-specific information

### Two-Stage Retrieval (Why Reranking?)

**Stage 1: Fast Retrieval (Top-15)**

- SentenceTransformer is lightweight and fast
- Good for initial filtering from large dataset
- May have some false positives

**Stage 2: Precise Reranking (Top-5)**

- FlagReranker is more accurate but slower
- Cross-attention between query and document
- Refines results to most relevant chunks

**Analogy:** Like a funnel - cast wide net first, then carefully select best items.

---

## Response Quality Measurement

### Built-in Mechanisms:

1. **User Feedback System**

   ```python
   cursor.execute(
       "UPDATE user_feedback SET feedback = %s WHERE id = %s",
       (feedback_type, response_id)
   )
   ```

   - Thumbs up/down for each response
   - Stored in database for analysis

2. **Potential Metrics** (not implemented but can be added):
   - **Feedback Rate**: % of positive vs negative feedback
   - **Response Time**: Track latency of each pipeline stage
   - **Context Relevance**: Log similarity scores from retrieval
   - **Answer Rate**: % of queries that return "Couldn't find the answer"

### How to Measure Quality (Interview Answer):

**Quantitative:**

- Feedback ratio (thumbs up / total feedback)
- Average similarity scores of retrieved documents
- Response latency benchmarks

**Qualitative:**

- Manual review of sample responses
- A/B testing different retrieval strategies
- User surveys on answer helpfulness

**Example Implementation:**

```python
# Calculate feedback metrics
positive_feedback = cursor.execute(
    "SELECT COUNT(*) FROM user_feedback WHERE feedback = 1"
).fetchone()[0]
total_feedback = cursor.execute(
    "SELECT COUNT(*) FROM user_feedback WHERE feedback IS NOT NULL"
).fetchone()[0]
satisfaction_rate = positive_feedback / total_feedback
```

---

## Database Schema

### `aiml_dataset` Table

- `source`: Document source/reference
- `text`: Text chunk
- `embedding`: 384-dimensional vector (pgvector)

### `user_feedback` Table

- `id`: Primary key
- `query`: User question
- `answer`: Generated response
- `feedback`: 1 (positive) or 0 (negative)

---

## Performance Optimizations

1. **Vector Indexing**: pgvector uses HNSW/IVFFlat for fast similarity search
2. **FP16 Precision**: `use_fp16=True` speeds up reranker with minimal accuracy loss
3. **Batch Processing**: SentenceTransformer can encode multiple queries at once
4. **Connection Pooling**: Could add for production (currently creates new connection each time)

---

## Potential Improvements

1. **Caching**: Store embeddings for common queries
2. **Async Processing**: Use async/await for parallel retrieval + LLM calls
3. **Monitoring**: Add logging for similarity scores, response times
4. **Evaluation Dataset**: Create test set with ground truth answers
5. **Hybrid Search**: Combine vector search with keyword search (BM25)
6. **Streaming**: Stream LLM responses for better UX

---

## Interview Talking Points

### Challenges Solved:

- **Hallucination Prevention**: System prompt constrains LLM to context only
- **Relevance**: Two-stage retrieval ensures high-quality context
- **Scalability**: Vector database handles large document collections efficiently

### Design Decisions:

- **Why Llama3-70B?**: Good balance of quality and speed via Groq
- **Why all-MiniLM-L6-v2?**: Lightweight, fast, good for semantic search
- **Why PostgreSQL?**: Familiar, reliable, pgvector extension for vectors

### Real-World Applications:

- Internal knowledge base chatbot
- Customer support automation
- Documentation Q&A system
- Research paper exploration tool
