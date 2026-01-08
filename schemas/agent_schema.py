# schemas/chat.py
from datetime import datetime
from typing import Optional, List

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field


# =======================
# 1. 请求参数 (Request)
# =======================

class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "example": {
            "question": '今天天气怎么样',
            "thread_id": '123-123'
        }
    })
    question: str = Field(..., description="用户问题")
    thread_id: str | None = Field(None, description="会话id")


class DrawRequest(BaseModel):
    file_name: str


class HistoryFeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "example": {
            "history_id": 10086,
            "thread_id": '111-xxx',
            "limit": 1
        }
    })

    limit: int = Query(10, ge=1, le=100, description="每页条数")
    history_id: Optional[int] = Query(None, description="最早一条消息ID")
    thread_id: Optional[str] = Query(None, description="会话ID")


class HistoryTableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "example": {
            "page": 1,
            "limit": 10,
            'user_id': 1314
        }
    })

    limit: int = Query(10, ge=1, le=100, description="每页条数")
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
            'user_id': 1314
        }
    })

    user_id: int = Field(..., ge=0, description="用户id")


# =======================
# 2. 响应参数 (Response)
# =======================

class HistorySchema(BaseModel):
    # 关键配置：允许从 ORM 对象读取数据 (旧版叫 orm_mode = True)
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    created_at: datetime
    thread_id: str
    user_id: int


class ThreadSchema(BaseModel):
    # 关键配置：允许从 ORM 对象读取数据 (旧版叫 orm_mode = True)
    model_config = ConfigDict(from_attributes=True)

    thread_id: str
    title: str


class HistoryTableResponse(BaseModel):
    total_count: int
    data: List[HistorySchema]


class HistoryFeedResponse(BaseModel):
    has_more: bool
    data: List[HistorySchema]


class ThreadResponse(BaseModel):
    # has_more: bool
    data: List[ThreadSchema]
