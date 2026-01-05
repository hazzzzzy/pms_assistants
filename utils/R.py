from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


# 你的泛型模型
class BaseResponse(BaseModel, Generic[T]):
    code: int = 0
    msg: str = "操作成功"
    data: T | None = None


class R:
    @staticmethod
    def success(data: T = None, msg: str = "操作成功"):
        return BaseResponse(code=0, data=data, msg=msg)

    @staticmethod
    def fail(msg: str = "操作失败", code: int = -1, ):
        # 注意：这里我们返回的是字典，稍后在 main.py 里我们会处理让它 HTTP 状态码变 200
        # return JSONResponse(
        #     status_code=200,  # 强制 HTTP 状态码为 200
        #     content={
        #         "code": code,
        #         "msg": msg,
        #         "data": data
        #     }
        # )
        return BaseResponse(msg=msg, code=code)
