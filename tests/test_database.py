"""Tests for ORM models and database layer using an in-memory SQLite database."""
import pytest
from datetime import timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import Base
from app.models import Conversation, Message


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    with Session(engine) as session:
        yield session
    Base.metadata.drop_all(bind=engine)


# ── Conversation ──────────────────────────────────────────────────────────────

class TestConversationModel:
    def test_create_conversation(self, db):
        convo = Conversation(title="Wind Load Analysis")
        db.add(convo)
        db.commit()
        assert convo.id is not None
        assert convo.title == "Wind Load Analysis"

    def test_default_title(self, db):
        convo = Conversation()
        db.add(convo)
        db.commit()
        assert convo.title == "New Conversation"

    def test_created_at_set_automatically(self, db):
        convo = Conversation(title="Test")
        db.add(convo)
        db.commit()
        assert convo.created_at is not None

    def test_updated_at_set_automatically(self, db):
        convo = Conversation(title="Test")
        db.add(convo)
        db.commit()
        assert convo.updated_at is not None

    def test_multiple_conversations(self, db):
        for i in range(3):
            db.add(Conversation(title=f"Conversation {i}"))
        db.commit()
        assert db.query(Conversation).count() == 3

    def test_delete_conversation(self, db):
        convo = Conversation(title="To Delete")
        db.add(convo)
        db.commit()
        db.delete(convo)
        db.commit()
        assert db.query(Conversation).count() == 0


# ── Message ───────────────────────────────────────────────────────────────────

class TestMessageModel:
    def test_create_message(self, db):
        convo = Conversation(title="Test")
        db.add(convo)
        db.commit()

        msg = Message(conversation_id=convo.id, role="user", content="Hello")
        db.add(msg)
        db.commit()

        assert msg.id is not None
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_belongs_to_conversation(self, db):
        convo = Conversation(title="Test")
        db.add(convo)
        db.commit()

        db.add(Message(conversation_id=convo.id, role="user", content="Q"))
        db.add(Message(conversation_id=convo.id, role="assistant", content="A"))
        db.commit()

        db.refresh(convo)
        assert len(convo.messages) == 2

    def test_messages_ordered_by_created_at(self, db):
        from datetime import datetime, timezone, timedelta
        convo = Conversation(title="Test")
        db.add(convo)
        db.commit()

        now = datetime.now(timezone.utc)
        db.add(Message(conversation_id=convo.id, role="user", content="First",
                       created_at=now))
        db.add(Message(conversation_id=convo.id, role="assistant", content="Second",
                       created_at=now + timedelta(seconds=1)))
        db.commit()

        db.refresh(convo)
        assert convo.messages[0].content == "First"
        assert convo.messages[1].content == "Second"

    def test_cascade_delete_removes_messages(self, db):
        convo = Conversation(title="Test")
        db.add(convo)
        db.commit()

        db.add(Message(conversation_id=convo.id, role="user", content="Q"))
        db.add(Message(conversation_id=convo.id, role="assistant", content="A"))
        db.commit()

        db.delete(convo)
        db.commit()

        assert db.query(Message).count() == 0

    def test_user_and_assistant_roles(self, db):
        convo = Conversation(title="Test")
        db.add(convo)
        db.commit()

        user_msg = Message(conversation_id=convo.id, role="user", content="Q")
        ai_msg = Message(conversation_id=convo.id, role="assistant", content="A")
        db.add_all([user_msg, ai_msg])
        db.commit()

        roles = {m.role for m in convo.messages}
        assert roles == {"user", "assistant"}

    def test_messages_isolated_across_conversations(self, db):
        c1 = Conversation(title="C1")
        c2 = Conversation(title="C2")
        db.add_all([c1, c2])
        db.commit()

        db.add(Message(conversation_id=c1.id, role="user", content="Q in C1"))
        db.add(Message(conversation_id=c2.id, role="user", content="Q in C2"))
        db.commit()

        db.refresh(c1)
        db.refresh(c2)
        assert len(c1.messages) == 1
        assert len(c2.messages) == 1
        assert c1.messages[0].content != c2.messages[0].content
