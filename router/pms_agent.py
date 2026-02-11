from typing import Annotated

from fastapi import APIRouter, Request, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from core.agent_context import AgentContext
from schemas.pms_agent_schema import DrawRequest, FeedbackRequest, HistoryTableResponse, HistoryTableRequest, HistoryFeedRequest, \
    HistoryFeedResponse, ThreadResponse, ThreadRequest, PresetQuestionResponse, PresetQuestionRequest, AllUserResponse
from service import pms_agent_service
from utils.R import BaseResponse

agent_router = APIRouter(prefix="/pms_agent", tags=["pms_agent"])


@agent_router.post('/chat', summary='聊天(支持文件)', description='支持上传xlsx进行分析')
async def chat(
        request: Request,
        question: Annotated[str, Form(description="用户问题")],
        hotel_id: Annotated[int, Form(description="酒店ID")],
        user_id: Annotated[int, Form(description="用户ID")],
        thread_id: Annotated[str | None, Form(description="会话ID，新建会话无需传递，继续会话需要传递")] = None,
        file: Annotated[UploadFile | None, File(description="上传的Excel文件")] = None
):
    context = AgentContext(request.app, include_graph=True)
    gen = pms_agent_service.chat(context, file, question, thread_id, hotel_id, user_id)
    return StreamingResponse(gen, media_type="text/event-stream")


@agent_router.post('/draw', deprecated=True)
async def draw(request: Request, req: DrawRequest):
    context = AgentContext(request.app, include_graph=True)
    return await pms_agent_service.draw(context, req.file_name)


@agent_router.get('/get_history_feed', response_model=BaseResponse[HistoryFeedResponse], summary='获取聊天记录瀑布流（对话框）')
async def get_history_feed(req: HistoryFeedRequest = Query()):
    return await pms_agent_service.get_history_feed(limit=req.limit, history_id=req.history_id, thread_id=req.thread_id)


@agent_router.get('/get_history_table', response_model=BaseResponse[HistoryTableResponse], summary='获取聊天记录表格', deprecated=True)
async def get_history_table(req: HistoryTableRequest = Query()):
    return await pms_agent_service.get_history_table(limit=req.limit, page=req.page)


@agent_router.post('/feedback', summary='对AI的回答进行反馈（赞/踩）', description='''
## feedback 0-无反馈 1-赞 2-踩
''')
async def feedback(req: FeedbackRequest):
    return await pms_agent_service.get_feedback(history_id=req.history_id, feedback=req.feedback)


@agent_router.get('/get_user_thread', response_model=BaseResponse[ThreadResponse], summary='获取用户会话列表')
async def get_user_thread(req: ThreadRequest = Query()):
    return await pms_agent_service.get_user_thread(before_id=req.id, user_id=req.user_id, hotel_id=req.hotel_id, limit=req.limit)


@agent_router.get('/get_preset_question', response_model=BaseResponse[PresetQuestionResponse], summary='获取预设问题列表')
async def get_preset_question(req: PresetQuestionRequest = Query()):
    return await pms_agent_service.get_preset_question(limit=req.limit, page=req.page)


@agent_router.get('/get_all_user', response_model=BaseResponse[AllUserResponse], summary='获取全部使用过的用户信息')
async def get_all_user():
    return await pms_agent_service.get_all_user()
