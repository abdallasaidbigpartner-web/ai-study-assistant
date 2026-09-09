# AI Study Assistant

A complete, production-style backend system combining authentication, a real relational database, and Retrieval-Augmented Generation (RAG) into a single working application. This project is a capstone that integrates skills developed across a broader software and AI engineering learning path, demonstrating the ability to design, build, secure, and operate a real system end-to-end - not just isolated exercises.

## Problem It Solves

Students often ask questions that are already answered in their own course material, but sifting through notes to find the right answer is slow. This system lets a student ask a question in plain language and receive an answer generated from their actual course notes - grounded in real, verifiable content rather than a model's general (and potentially incorrect or outdated) training knowledge.

## Architecture

    Client (curl / frontend)
        |
        v
    FastAPI application (main.py)
        |
        |-- POST /register  --> bcrypt password hashing --> PostgreSQL (app_users, via connection pool)
        |-- POST /login     --> bcrypt verification      --> issues a signed JWT access token
        |-- POST /ask        --> requires valid JWT
        |                     --> TF-IDF retrieval          --> PostgreSQL (course_notes, via connection pool)
        |                     --> top-matching notes as context
        |                     --> Groq LLM API (grounded answer generation)
        |-- GET  /health     --> service status, version, uptime

**Design principle:** the LLM never answers from memory alone. Every response to `/ask` is grounded in retrieved course notes, and the model is explicitly instructed to say so if the notes don't cover the question - avoiding hallucinated answers, a known failure mode of naive LLM applications.

## Tech Stack & Why

| Component | Choice | Reason |
|-----------|--------|--------|
| Web framework | FastAPI | Async-capable, automatic request validation via Pydantic, industry-standard for Python APIs |
| Database | PostgreSQL | Relational integrity (foreign keys, constraints), industry-standard for production systems |
| DB driver | psycopg2 + connection pool | `psycopg2.pool.SimpleConnectionPool` reuses connections across requests instead of opening/closing one per request |
| Password security | bcrypt | Purpose-built, slow-by-design hashing algorithm resistant to brute-force attacks |
| Session auth | JWT (python-jose) | Stateless, signed tokens - the client holds the session, not the server, which scales better than server-side sessions |
| Retrieval | scikit-learn (TF-IDF + cosine similarity) | Reliable, dependency-light semantic search; scales to embeddings-based retrieval without changing the architecture |
| LLM inference | Groq API (`openai/gpt-oss-20b`) | Low-latency inference suitable for interactive use |
| Validation | Pydantic | Rejects malformed input before it reaches business logic or the database |
| Observability | Python `logging` + `/health` endpoint | Standard practice for production services - enables monitoring, debugging, and load-balancer health checks |

## Security Considerations

- Passwords are never stored in plain text; only bcrypt hashes are persisted.
- Sessions use signed JWTs (HS256) with a 60-minute expiration; the server never stores session state.
- All SQL queries use parameterized statements (`%s` placeholders), preventing SQL injection.
- Input is validated at the API boundary (username length, password strength) before touching the database.
- The Groq API key and JWT signing secret are read from environment variables, never hardcoded in source.

## Running Locally

    pip install -r requirements.txt
    export GROQ_API_KEY=your_key_here
    export JWT_SECRET=a_long_random_secret_string
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

## Example Usage

    # Register a user
    curl -X POST http://localhost:8000/register \
      -H "Content-Type: application/json" \
      -d '{"username": "student1", "password": "StudyHard123"}'

    # Log in - returns a JWT
    curl -X POST http://localhost:8000/login \
      -H "Content-Type: application/json" \
      -d '{"username": "student1", "password": "StudyHard123"}'

    # Ask a question, authenticated with the JWT from login
    curl -X POST http://localhost:8000/ask \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer <your_token_here>" \
      -d '{"question": "What is overfitting in machine learning?"}'

## Endpoints

| Endpoint | Method | Auth Required | Description |
|----------|--------|----------------|-------------|
| `/health` | GET | No | Returns service status, version, and uptime |
| `/register` | POST | No | Creates a new user with a bcrypt-hashed password |
| `/login` | POST | No | Verifies credentials, returns a JWT access token |
| `/ask` | POST | Yes (Bearer token) | Retrieves relevant course notes and returns an LLM-generated, grounded answer |

## Known Limitations & Future Improvements

- **Retrieval method:** currently uses TF-IDF (keyword-based), which can miss conceptually related content that shares no exact words. A production upgrade would use neural embeddings for true semantic matching.
- **No token refresh/revocation:** tokens are valid until they expire (60 minutes); there is no refresh-token flow or server-side revocation list yet.
- **No containerization yet for this specific project:** the broader learning-journey repos include Docker + CI examples; applying that same pattern here is a natural next step.

## Related Repositories

This project draws on skills developed in a structured learning path:
- [python-learning-journey](https://github.com/abdallasaidbigpartner-web/python-learning-journey) - Python fundamentals through backend engineering, machine learning, deep learning, and Generative AI
- [typescript-learning-journey](https://github.com/abdallasaidbigpartner-web/typescript-learning-journey) - TypeScript fundamentals through classes, async/await, and automated testing
- [sql-learning-journey](https://github.com/abdallasaidbigpartner-web/sql-learning-journey) - SQL and PostgreSQL fundamentals through transactions, indexing, and query optimization
