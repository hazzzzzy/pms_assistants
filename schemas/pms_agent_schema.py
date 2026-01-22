# schemas/chat.py
from datetime import datetime
from typing import Optional, List, Literal

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, ValidationError


# =======================
# 1. 请求参数 (Request)
# =======================

class RouteOut(BaseModel):
    route: Literal["SQL", "CHAT"]
    confidence: float = Field(ge=0, le=1)


def parse_route(text: str) -> RouteOut | None:
    try:
        return RouteOut.model_validate_json(text)
    except ValidationError:
        return None


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "example": {
            "question": '今天天气怎么样',
            "thread_id": '123-123',
            'hotel_id': 100785,
            'user_id': 1111,
            # 'user_thread_id': 1111,
        }
    })
    question: str = Field(..., description="用户问题")
    thread_id: str | None = Field(None, description="会话id")
    hotel_id: int = Field(..., ge=0, description="酒店id")
    user_id: int = Field(..., ge=0, description="员工id")
    # user_thread_id: int | None = Field(None, description="用户与会话的关联ID")


class DrawRequest(BaseModel):
    file_name: str


class HistoryFeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "example": {
            "history_id": 10086,
            "thread_id": '123-123',
            "limit": 1
        }
    })

    limit: int = Query(10, ge=10, le=100, description="每页条数")
    history_id: Optional[int] = Query(None, description="若传入，则获取该id以前 {limit} 条数据")
    thread_id: str = Field(..., description="会话id")


class HistoryTableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "example": {
            "page": 1,
            "limit": 10,
            'user_id': 1314
        }
    })

    limit: int = Query(10, ge=10, le=100, description="每页条数")
    page: int = Query(1, ge=1, description="页码")
    user_id: int = Query(1, ge=1, description="用户id")


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "example": {
            "history_id": 10,
            "feedback": 1
        }
    })

    feedback: int = Field(..., ge=0, le=2, description="0-无反馈 1-赞 2-踩")
    history_id: int = Field(..., ge=1, description="聊天记录id")


class ThreadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "example": {
            'id': 1314,
            'user_id': 1314,
            'hotel_id': 1314,
            'limit': 10
        }
    })

    id: int | None = Query(None, ge=0, description="若传入，则获取该id以前 {limit} 条数据")
    user_id: int = Query(..., ge=0, description="用户id")
    hotel_id: int = Query(..., ge=0, description="酒店id")
    limit: int = Query(10, ge=10, le=100, description="每次获取的条数")


class PresetQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "example": {
            'limit': 10,
            'page': 1,
        }
    })

    limit: int = Query(10, ge=1, le=100, description="每次获取的条数")
    page: int = Query(1, ge=1, le=100, description="页码")


# =======================
# 2. 数据结构
# =======================

class HistorySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    created_at: datetime
    thread_id: str
    file_name: str | None
    feedback: int


class ThreadSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    thread_id: str
    title: str
    created_at: datetime


class PresetQuestionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str


# =======================
# 3. 响应参数 (Response)
# =======================

class HistoryTableResponse(BaseModel):
    total_count: int
    data: List[HistorySchema]


class HistoryFeedResponse(BaseModel):
    has_more: bool
    data: List[HistorySchema]


class ThreadResponse(BaseModel):
    has_more: bool
    data: List[ThreadSchema]


class PresetQuestionResponse(BaseModel):
    data: List[PresetQuestionSchema]
    total_count: int
