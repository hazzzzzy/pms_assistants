from typing import Generic, TypeVar, Optional

from pydantic import BaseModel

# 定义一个泛型变量，用于动态替换 data 的内容
T = TypeVar("T")


# 标准响应结构
class BaseResponse(BaseModel, Generic[T]):
    code: int = 200
    msg: str = "success"
    data: Optional[T] = None

# 这里的 Generic[T] 很重要，它能让你的 Swagger 文档显示出 data 具体是哪个模型
