from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from core.agent_context import AgentContext
from service import agent_service

agent_router = APIRouter(prefix="/agent", tags=["agent"])


class ChatRequest(BaseModel):
    question: str
    thread_id: str


@agent_router.post('/chat')
async def chat(req: ChatRequest,
               request: Request,
               hotel_id: str = Header(..., alias='hotel_id'),
               uid: str = Header(..., alias='uid')):
    context = AgentContext(request.app, include_graph=True)
    gen = agent_service.chat(context, req.question, req.thread_id, hotel_id, uid)
    return StreamingResponse(gen, media_type="text/event-stream")
