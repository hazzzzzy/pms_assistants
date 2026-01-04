# schemas/chat.py
from datetime import datetime
from typing import Optional, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


# =======================
# 1. 请求参数 (Request)
# =======================

class ChatRequest(BaseModel):
    question: str
    thread_id: str


class DrawRequest(BaseModel):
    file_name: str


class HistoryFeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["feed"]
    limit: int = Field(10, ge=1, le=100, description="每页条数")
    history_id: Optional[int] = Field(None, description="最早一条消息ID")


class HistoryTableRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["table"] = "table"
    limit: int = Field(10, ge=1, le=100, description="每页条数")
    page: int = Field(1, ge=1, description="页码")


HistoryRequest = Union[HistoryFeedRequest, HistoryTableRequest]


# =======================
# 2. 响应参数 (Response)
# =======================

class ChatHistorySchema(BaseModel):
    # 关键配置：允许从 ORM 对象读取数据 (旧版叫 orm_mode = True)
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    created_at: datetime
    thread_id: str
    uid: int


class HistoryListResponse(BaseModel):
    """
    最终返回给前端的大对象
    """
    total: int
    page: int
    limit: int
    # data: List[ChatHistoryItem]  # 嵌套上面的 Item 类
