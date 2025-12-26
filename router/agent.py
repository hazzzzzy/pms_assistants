from fastapi import APIRouter, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from service import agent_service

agent_router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    question: str
    thread_id: str


@agent_router.post('/chat')
async def chat(req: ChatRequest,
               hotel_id: str = Header(..., alias='hotel_id'),
               uid: str = Header(..., alias='uid')):
    gen = agent_service.chat(req.question, req.thread_id, hotel_id, uid)
    return StreamingResponse(gen, media_type="text/event-stream")
