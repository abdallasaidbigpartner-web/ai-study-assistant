"""
Automated tests for the AI Study Assistant capstone.

Uses FastAPI's TestClient for endpoint-level tests, and mocks the
Groq API call in the /ask test to avoid real network calls during
testing - the same professional pattern used in the learning-journey
repos' test suites.
"""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from main import app, retrieve_relevant_notes

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "uptime_seconds" in data


def test_register_rejects_short_username():
    response = client.post("/register", json={"username": "ab", "password": "ValidPass123"})
    assert response.status_code == 422


def test_register_rejects_short_password():
    response = client.post("/register", json={"username": "validuser", "password": "short"})
    assert response.status_code == 422


def test_login_rejects_nonexistent_user():
    response = client.post("/login", json={"username": "definitely_not_a_real_user_xyz", "password": "whatever123"})
    assert response.status_code == 401


def test_retrieve_relevant_notes_returns_results():
    """Verify retrieval returns notes from the real database (integration test)."""
    results = retrieve_relevant_notes("What is overfitting?")
    assert len(results) > 0
    assert "topic" in results[0]
    assert "content" in results[0]


@patch("main.client")
def test_ask_endpoint_with_mocked_llm(mock_groq_client):
    """Verify /ask correctly assembles a response, without a real LLM call."""
    mock_response = MagicMock()
    mock_response.choices[0].message.content = "Mocked grounded answer."
    mock_groq_client.chat.completions.create.return_value = mock_response

    response = client.post("/ask", json={"question": "What is overfitting?"})

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Mocked grounded answer."
    assert "sources" in data
