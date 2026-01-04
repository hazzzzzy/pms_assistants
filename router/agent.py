from fastapi import APIRouter, Header, Request, Depends
from fastapi.responses import StreamingResponse

from core.agent_context import AgentContext
from schemas.agent import ChatRequest, DrawRequest, HistoryRequest, HistoryFeedRequest
from service import agent_service

agent_router = APIRouter(prefix="/agent", tags=["agent"])


@agent_router.post('/chat')
async def chat(req: ChatRequest,
               request: Request,
               hotel_id: str = Header(..., alias='hotel_id'),
               uid: str = Header(..., alias='uid')):
    context = AgentContext(request.app, include_graph=True)
    gen = agent_service.chat(context, req.question, req.thread_id, hotel_id, uid)
    return StreamingResponse(gen, media_type="text/event-stream")


@agent_router.post('/draw')
async def chat(request: Request, req: DrawRequest):
    context = AgentContext(request.app, include_graph=True)
    return await agent_service.draw(context, req.file_name)


@agent_router.get('/get_history')
async def get_history(req: HistoryRequest = Depends()):
    if isinstance(req, HistoryFeedRequest):
        return await agent_service.get_history_feed(limit=req.limit, history_id=req.history_id)
    return await agent_service.get_history_table(limit=req.limit, page=req.page)
