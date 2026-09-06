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
        |-- POST /register  --> bcrypt password hashing --> PostgreSQL (app_users)
        |-- POST /login     --> bcrypt verification      --> PostgreSQL (app_users)
        |-- POST /ask        --> TF-IDF retrieval          --> PostgreSQL (course_notes)
        |                     --> top-matching notes as context
        |                     --> Groq LLM API (grounded answer generation)
        |-- GET  /health     --> service status, version, uptime

**Design principle:** the LLM never answers from memory alone. Every response to `/ask` is grounded in retrieved course notes, and the model is explicitly instructed to say so if the notes don't cover the question - avoiding hallucinated answers, a known failure mode of naive LLM applications.

## Tech Stack & Why

| Component | Choice | Reason |
|-----------|--------|--------|
| Web framework | FastAPI | Async-capable, automatic request validation via Pydantic, industry-standard for Python APIs |
| Database | PostgreSQL | Relational integrity (foreign keys, constraints), industry-standard for production systems |
| DB driver | psycopg2 | Mature, widely-used PostgreSQL adapter for Python |
| Password security | bcrypt | Purpose-built, slow-by-design hashing algorithm resistant to brute-force attacks |
| Retrieval | scikit-learn (TF-IDF + cosine similarity) | Reliable, dependency-light semantic search; scales to embeddings-based retrieval without changing the architecture |
| LLM inference | Groq API (`openai/gpt-oss-20b`) | Low-latency inference suitable for interactive use |
| Validation | Pydantic | Rejects malformed input before it reaches business logic or the database |
| Observability | Python `logging` + `/health` endpoint | Standard practice for production services - enables monitoring, debugging, and load-balancer health checks |

## Security Considerations

- Passwords are never stored in plain text; only bcrypt hashes are persisted.
- All SQL queries use parameterized statements (`%s` placeholders), preventing SQL injection.
- Input is validated at the API boundary (username length, password strength) before touching the database.
- The Groq API key is read from an environment variable, never hardcoded in source.

## Running Locally

    pip install -r requirements.txt
    export GROQ_API_KEY=your_key_here
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

## Example Usage

    curl -X POST http://localhost:8000/register \
      -H "Content-Type: application/json" \
      -d '{"username": "student1", "password": "StudyHard123"}'

    curl -X POST http://localhost:8000/ask \
      -H "Content-Type: application/json" \
      -d '{"question": "What is overfitting in machine learning?"}'

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Returns service status, version, and uptime - used for monitoring |
| `/register` | POST | Creates a new user with a bcrypt-hashed password |
| `/login` | POST | Verifies credentials against the stored hash |
| `/ask` | POST | Retrieves relevant course notes and returns an LLM-generated, grounded answer |

## Known Limitations & Future Improvements

- **Retrieval method:** currently uses TF-IDF (keyword-based), which can miss conceptually related content that shares no exact words. A production upgrade would use neural embeddings for true semantic matching.
- **No session/token-based auth yet:** login verifies credentials per-request rather than issuing a session token (e.g. JWT).
- **Single-instance database connections:** a production deployment would use a connection pool for efficiency under load.

## Related Repositories

This project draws on skills developed in a structured learning path:
- [python-learning-journey](https://github.com/abdallasaidbigpartner-web/python-learning-journey)
- [typescript-learning-journey](https://github.com/abdallasaidbigpartner-web/typescript-learning-journey)
- [sql-learning-journey](https://github.com/abdallasaidbigpartner-web/sql-learning-journey)
