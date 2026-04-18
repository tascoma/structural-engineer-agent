from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Role = Literal["user", "assistant"]


class MessageIn(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: int
    role: Role
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: int
    title: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(BaseModel):
    id: int
    title: str
    messages: list[MessageOut]

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    conversation_id: int
    message: MessageOut
