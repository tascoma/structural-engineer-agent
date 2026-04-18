"""Integration tests for FastAPI routes using an in-memory database.

The AI agent (run_agent) is mocked so tests run without an Anthropic API key
and complete instantly.
"""
import pytest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Conversation, Message


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def db_engine():
    # StaticPool keeps a single connection so all sessions share the same in-memory DB.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session(db_engine):
    TestingSession = sessionmaker(bind=db_engine)
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture
def client(db_engine):
    TestingSession = sessionmaker(bind=db_engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, follow_redirects=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def conversation(db_session):
    """A saved conversation with no messages."""
    convo = Conversation(title="Test Conversation")
    db_session.add(convo)
    db_session.commit()
    db_session.refresh(convo)
    return convo


@pytest.fixture
def conversation_with_messages(db_session):
    """A saved conversation that already has one exchange."""
    convo = Conversation(title="Beam Question")
    db_session.add(convo)
    db_session.commit()

    db_session.add(Message(conversation_id=convo.id, role="user", content="Size a beam"))
    db_session.add(Message(conversation_id=convo.id, role="assistant", content="Use W18x35"))
    db_session.commit()
    db_session.refresh(convo)
    return convo


# ── Homepage ──────────────────────────────────────────────────────────────────

class TestHomepage:
    def test_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_returns_html(self, client):
        response = client.get("/")
        assert "text/html" in response.headers["content-type"]

    def test_contains_app_name(self, client):
        response = client.get("/")
        assert "StructAI" in response.text


# ── List Conversations ────────────────────────────────────────────────────────

class TestListConversations:
    def test_empty_list(self, client):
        response = client.get("/conversations")
        assert response.status_code == 200
        assert response.json() == []

    def test_returns_saved_conversations(self, client, conversation):
        response = client.get("/conversations")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["id"] == conversation.id
        assert data[0]["title"] == "Test Conversation"

    def test_ordered_by_updated_at_desc(self, client, db_session):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        older = Conversation(title="Older", updated_at=now - timedelta(hours=1))
        newer = Conversation(title="Newer", updated_at=now)
        db_session.add_all([older, newer])
        db_session.commit()

        response = client.get("/conversations")
        titles = [c["title"] for c in response.json()]
        assert titles[0] == "Newer"
        assert titles[1] == "Older"


# ── New Conversation ──────────────────────────────────────────────────────────

class TestNewConversation:
    def test_creates_conversation_and_redirects(self, client):
        response = client.post("/conversations/new")
        assert response.status_code == 200  # TestClient follows redirect
        assert "/conversations/" in str(response.url)

    def test_conversation_appears_in_list(self, client):
        client.post("/conversations/new")
        response = client.get("/conversations")
        assert len(response.json()) == 1

    def test_default_title_is_new_conversation(self, client):
        client.post("/conversations/new")
        data = client.get("/conversations").json()
        assert data[0]["title"] == "New Conversation"


# ── Get Conversation ──────────────────────────────────────────────────────────

class TestGetConversation:
    def test_returns_200_for_existing(self, client, conversation):
        response = client.get(f"/conversations/{conversation.id}")
        assert response.status_code == 200

    def test_returns_html(self, client, conversation):
        response = client.get(f"/conversations/{conversation.id}")
        assert "text/html" in response.headers["content-type"]

    def test_returns_404_for_missing(self, client):
        response = client.get("/conversations/9999")
        assert response.status_code == 404

    def test_contains_prior_messages(self, client, conversation_with_messages):
        response = client.get(f"/conversations/{conversation_with_messages.id}")
        assert "Size a beam" in response.text
        assert "Use W18x35" in response.text


# ── Send Message ──────────────────────────────────────────────────────────────

class TestSendMessage:
    def test_returns_ai_response(self, client, conversation):
        with patch("app.routes.run_agent", new=AsyncMock(return_value="Net pressure is 32 psf.")):
            response = client.post(
                f"/conversations/{conversation.id}/messages",
                json={"content": "What is the wind pressure?"},
            )
        assert response.status_code == 200
        data = response.json()
        assert data["message"]["role"] == "assistant"
        assert data["message"]["content"] == "Net pressure is 32 psf."

    def test_returns_conversation_id(self, client, conversation):
        with patch("app.routes.run_agent", new=AsyncMock(return_value="Answer")):
            response = client.post(
                f"/conversations/{conversation.id}/messages",
                json={"content": "Question"},
            )
        assert response.json()["conversation_id"] == conversation.id

    def test_sets_title_from_first_message(self, client, conversation, db_session):
        with patch("app.routes.run_agent", new=AsyncMock(return_value="Answer")):
            client.post(
                f"/conversations/{conversation.id}/messages",
                json={"content": "Calculate wind load for a 30 ft building"},
            )
        db_session.refresh(conversation)
        assert "Calculate wind load" in conversation.title

    def test_title_not_overwritten_on_second_message(self, client, conversation_with_messages, db_session):
        original_title = conversation_with_messages.title
        with patch("app.routes.run_agent", new=AsyncMock(return_value="Answer")):
            client.post(
                f"/conversations/{conversation_with_messages.id}/messages",
                json={"content": "Follow-up question"},
            )
        db_session.refresh(conversation_with_messages)
        assert conversation_with_messages.title == original_title

    def test_long_message_truncated_in_title(self, client, conversation, db_session):
        long_msg = "A" * 200
        with patch("app.routes.run_agent", new=AsyncMock(return_value="Answer")):
            client.post(
                f"/conversations/{conversation.id}/messages",
                json={"content": long_msg},
            )
        db_session.refresh(conversation)
        assert len(conversation.title) <= 81  # 80 chars + ellipsis character

    def test_returns_404_for_missing_conversation(self, client):
        with patch("app.routes.run_agent", new=AsyncMock(return_value="Answer")):
            response = client.post(
                "/conversations/9999/messages",
                json={"content": "Hello"},
            )
        assert response.status_code == 404

    def test_messages_persisted_to_db(self, client, conversation, db_session):
        with patch("app.routes.run_agent", new=AsyncMock(return_value="Computed answer")):
            client.post(
                f"/conversations/{conversation.id}/messages",
                json={"content": "User question"},
            )
        messages = db_session.query(Message).filter_by(conversation_id=conversation.id).all()
        assert len(messages) == 2
        roles = {m.role for m in messages}
        assert roles == {"user", "assistant"}

    def test_history_passed_to_agent(self, client, conversation_with_messages):
        mock_agent = AsyncMock(return_value="New answer")
        with patch("app.routes.run_agent", new=mock_agent):
            client.post(
                f"/conversations/{conversation_with_messages.id}/messages",
                json={"content": "Follow up"},
            )
        mock_agent.assert_called_once()
        _, history = mock_agent.call_args[0]
        assert len(history) == 2  # one prior exchange = 2 messages in history


# ── Delete Conversation ───────────────────────────────────────────────────────

class TestDeleteConversation:
    def test_returns_204(self, client, conversation):
        response = client.delete(f"/conversations/{conversation.id}")
        assert response.status_code == 204

    def test_conversation_gone_after_delete(self, client, conversation):
        client.delete(f"/conversations/{conversation.id}")
        response = client.get("/conversations")
        assert response.json() == []

    def test_messages_deleted_with_conversation(self, client, conversation_with_messages, db_session):
        client.delete(f"/conversations/{conversation_with_messages.id}")
        count = db_session.query(Message).filter_by(
            conversation_id=conversation_with_messages.id
        ).count()
        assert count == 0

    def test_returns_404_for_missing(self, client):
        response = client.delete("/conversations/9999")
        assert response.status_code == 404
