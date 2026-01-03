# schemas/chat.py
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


# =======================
# 1. 请求参数 (Request)
# =======================

class HistoryQueryRequest(BaseModel):
    """
    用于接收 GET 请求的查询参数
    """
    limit: int = Field(10, ge=1, le=100, description="每页条数")
    page: int = Field(1, ge=1, description="页码")
    # 这里的 hid 前端可能不传，或者是 null
    hid: Optional[int] = Field(None, description="最后一条消息ID(瀑布流用)")


# =======================
# 2. 响应参数 (Response)
# =======================

class ChatHistoryItem(BaseModel):
    """
    单条聊天记录的结构
    """
    id: int
    question: str | None = None  # 允许为空
    answer: str | None = None
    created_at: datetime  # Pydantic 会自动把 datetime 转成 ISO 字符串

    # 关键配置：允许从 ORM 对象读取数据 (旧版叫 orm_mode = True)
    model_config = ConfigDict(from_attributes=True)


class HistoryListResponse(BaseModel):
    """
    最终返回给前端的大对象
    """
    total: int
    page: int
    limit: int
    data: List[ChatHistoryItem]  # 嵌套上面的 Item 类
