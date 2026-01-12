from fastapi import APIRouter, Request, Query, BackgroundTasks
from fastapi.responses import StreamingResponse

from core.agent_context import AgentContext
from schemas.agent_schema import ChatRequest, DrawRequest, FeedbackRequest, HistoryTableResponse, HistoryTableRequest, HistoryFeedRequest, \
    HistoryFeedResponse, ThreadResponse, ThreadRequest
from service import agent_service
from utils.R import BaseResponse

agent_router = APIRouter(prefix="/agent", tags=["agent"])


@agent_router.post('/chat', summary='聊天', description='''
## 先获取该用户的会话列表，假如有内容固定拿最早的会话作为历史记录，没有的话就为空
## 新建对话——thread_id传入null
## 继续对话——传入正确的thread_id
''')
async def chat(req: ChatRequest,
               request: Request,
               background_tasks: BackgroundTasks,
               # hotel_id: str = Header(..., alias='hotel_id', description='酒店id'),
               # user_id: str = Header(..., alias='user_id', description='员工id')
               ):
    context = AgentContext(request.app, include_graph=True)
    gen = agent_service.chat(context, background_tasks, req.question, req.thread_id, req.hotel_id, req.user_id)
    return StreamingResponse(gen, media_type="text/event-stream")


@agent_router.post('/draw', deprecated=True)
async def chat(request: Request, req: DrawRequest):
    context = AgentContext(request.app, include_graph=True)
    return await agent_service.draw(context, req.file_name)


@agent_router.get('/get_history_feed', response_model=BaseResponse[HistoryFeedResponse], summary='获取聊天记录瀑布流（对话框）')
async def get_history_feed(req: HistoryFeedRequest = Query()):
    return await agent_service.get_history_feed(limit=req.limit, history_id=req.history_id, thread_id=req.thread_id)


@agent_router.get('/get_history_table', response_model=BaseResponse[HistoryTableResponse], summary='获取聊天记录表格')
async def get_history_table(req: HistoryTableRequest = Query()):
    return await agent_service.get_history_table(limit=req.limit, page=req.page)


@agent_router.post('/feedback', summary='对AI的回答进行反馈（赞/踩）')
async def feedback(req: FeedbackRequest):
    return await agent_service.get_feedback(history_id=req.history_id, feedback=req.feedback)


@agent_router.get('/get_user_thread', response_model=BaseResponse[ThreadResponse], summary='获取用户会话列表')
async def get_user_thread(req: ThreadRequest = Query()):
    return await agent_service.get_user_thread(before_id=req.id, user_id=req.user_id, hotel_id=req.hotel_id, limit=req.limit)
