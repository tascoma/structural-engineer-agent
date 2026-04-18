from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart
from sqlalchemy.orm import Session

from .agents import run_agent
from .database import get_db
from .models import Conversation, Message
from .schemas import ChatResponse, ConversationDetail, ConversationSummary, MessageIn, MessageOut

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter()


def _build_history(messages: list[Message]) -> list[ModelMessage]:
    history: list[ModelMessage] = []
    for msg in messages:
        if msg.role == "user":
            history.append(ModelRequest(parts=[UserPromptPart(content=msg.content)]))
        else:
            history.append(ModelResponse(parts=[TextPart(content=msg.content)]))
    return history


def _get_conversations(db: Session) -> list[ConversationSummary]:
    convos = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return [ConversationSummary.model_validate(c) for c in convos]


@router.get("/")
def index(request: Request, db: Session = Depends(get_db)):
    conversations = _get_conversations(db)
    return templates.TemplateResponse(
        request,
        "index.html",
        {"conversations": conversations, "active_conversation": None, "messages": []},
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(db: Session = Depends(get_db)):
    return _get_conversations(db)


@router.post("/conversations/new")
def new_conversation(db: Session = Depends(get_db)):
    convo = Conversation(title="New Conversation")
    db.add(convo)
    db.commit()
    db.refresh(convo)
    return RedirectResponse(url=f"/conversations/{convo.id}", status_code=303)


@router.get("/conversations/{conversation_id}")
def get_conversation(conversation_id: int, request: Request, db: Session = Depends(get_db)):
    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    conversations = _get_conversations(db)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "conversations": conversations,
            "active_conversation": ConversationDetail.model_validate(convo),
            "messages": [MessageOut.model_validate(m) for m in convo.messages],
        },
    )


@router.post("/conversations/{conversation_id}/messages", response_model=ChatResponse)
async def send_message(conversation_id: int, body: MessageIn, db: Session = Depends(get_db)):
    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")

    history = _build_history(convo.messages)

    ai_response = await run_agent(body.content, history)

    now = datetime.now(timezone.utc)

    user_msg = Message(conversation_id=conversation_id, role="user", content=body.content, created_at=now)
    db.add(user_msg)
    db.flush()

    ai_msg = Message(conversation_id=conversation_id, role="assistant", content=ai_response, created_at=now)
    db.add(ai_msg)

    if not convo.messages:
        convo.set_title_from(body.content)

    convo.updated_at = now
    db.commit()
    db.refresh(ai_msg)

    return ChatResponse(conversation_id=conversation_id, message=MessageOut.model_validate(ai_msg))


@router.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: int, db: Session = Depends(get_db)):
    convo = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not convo:
        raise HTTPException(status_code=404, detail="Conversation not found")
    db.delete(convo)
    db.commit()
