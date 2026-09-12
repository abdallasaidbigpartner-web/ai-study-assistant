"""
AI Study Assistant - Capstone Project

A complete system combining:
- FastAPI backend with PostgreSQL persistence (via a connection pool)
- bcrypt-hashed authentication with JWT session tokens
- RAG (Retrieval-Augmented Generation): semantic search over course
  notes + LLM grounding, so answers are based on real course content
- Structured logging and a health check endpoint for observability

This integrates the individual skills built across the Python,
backend, ML, and GenAI lessons into one cohesive, deployable system.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

import bcrypt
import psycopg2
import psycopg2.pool
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from groq import Groq
from jose import jwt, JWTError
from pydantic import BaseModel, field_validator
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("ai_study_assistant")

app = FastAPI(title="AI Study Assistant", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = Groq(api_key=os.environ.get("GROQ_API_KEY"))
APP_VERSION = "1.1.0"
_startup_time = datetime.now(timezone.utc)

# --- JWT configuration ---
JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = 60

security = HTTPBearer()

# --- Connection pool ---
# A pool of reusable connections, instead of opening/closing one per request.
# minconn=1, maxconn=5 is reasonable for a small service; tune for real load.
connection_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=1, maxconn=5, dbname="mydb"
)


def get_connection():
    """Borrow a connection from the pool."""
    return connection_pool.getconn()


def release_connection(conn):
    """Return a connection to the pool instead of closing it."""
    connection_pool.putconn(conn)


def create_access_token(username: str) -> str:
    """Create a signed JWT containing the username and an expiration time."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {"sub": username, "exp": expire}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Decode and validate a JWT, returning the username it belongs to."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return username
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


class UserCredentials(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def username_valid(cls, value: str) -> str:
        if len(value) < 3:
            raise ValueError("Username must be at least 3 characters")
        return value

    @field_validator("password")
    @classmethod
    def password_strong(cls, value: str) -> str:
        if len(value) < 8:
            raise ValueError("Password must be at least 8 characters")
        return value


class QuestionRequest(BaseModel):
    question: str


@app.get("/health")
def health_check():
    uptime_seconds = (datetime.now(timezone.utc) - _startup_time).total_seconds()
    return {"status": "healthy", "version": APP_VERSION, "uptime_seconds": round(uptime_seconds, 2)}


@app.post("/register")
def register(credentials: UserCredentials):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM app_users WHERE username = %s", (credentials.username,))
        if cursor.fetchone() is not None:
            raise HTTPException(status_code=400, detail="Username already exists")

        hashed = bcrypt.hashpw(credentials.password.encode(), bcrypt.gensalt())
        cursor.execute(
            "INSERT INTO app_users (username, password_hash) VALUES (%s, %s)",
            (credentials.username, hashed),
        )
        conn.commit()
        cursor.close()
    finally:
        release_connection(conn)

    logger.info(f"New user registered: {credentials.username}")
    return {"message": f"User '{credentials.username}' registered successfully"}


@app.post("/login")
def login(credentials: UserCredentials):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM app_users WHERE username = %s", (credentials.username,))
        row = cursor.fetchone()
        cursor.close()
    finally:
        release_connection(conn)

    if row is None or not bcrypt.checkpw(credentials.password.encode(), bytes(row[0])):
        logger.warning(f"Failed login attempt for username: {credentials.username}")
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = create_access_token(credentials.username)
    logger.info(f"User logged in: {credentials.username}")
    return {"access_token": token, "token_type": "bearer"}


def retrieve_relevant_notes(query: str, top_n: int = 2) -> list[dict]:
    """Retrieve the most relevant course notes using TF-IDF + cosine similarity."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT topic, content FROM course_notes")
        rows = cursor.fetchall()
        cursor.close()
    finally:
        release_connection(conn)

    documents = [row[1] for row in rows]
    topics = [row[0] for row in rows]

    vectorizer = TfidfVectorizer()
    all_texts = documents + [query]
    tfidf_matrix = vectorizer.fit_transform(all_texts)

    query_vector = tfidf_matrix[-1]
    doc_vectors = tfidf_matrix[:-1]
    similarities = cosine_similarity(query_vector, doc_vectors)[0]
    top_indices = similarities.argsort()[::-1][:top_n]

    return [{"topic": topics[i], "content": documents[i]} for i in top_indices]


@app.post("/ask")
def ask_question(request: QuestionRequest, current_user: str = Depends(verify_token)):
    """RAG endpoint: requires a valid JWT. Retrieves relevant course notes, then answers grounded in them."""
    logger.info(f"Question from {current_user}: {request.question}")

    relevant_notes = retrieve_relevant_notes(request.question)
    context = "\n".join(f"[{note['topic']}]: {note['content']}" for note in relevant_notes)

    prompt = f"""Answer the student's question using ONLY the course notes below. If the notes don't cover it, say so clearly.

Course Notes:
{context}

Question: {request.question}"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
    )
    answer = response.choices[0].message.content

    logger.info(f"Answer generated for {current_user}'s question")

    return {
        "question": request.question,
        "answer": answer,
        "sources": [note["topic"] for note in relevant_notes],
        "asked_by": current_user,
    }
