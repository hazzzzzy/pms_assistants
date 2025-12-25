from typing import Any

from fastapi.responses import JSONResponse


class R:
    @staticmethod
    def success(data: Any = None, msg: str = "操作成功"):
        return {
            "code": 200,
            "msg": msg,
            "data": data
        }

    @staticmethod
    def fail(code: int = 400, msg: str = "操作失败", data: Any = None):
        # 注意：这里我们返回的是字典，稍后在 main.py 里我们会处理让它 HTTP 状态码变 200
        return JSONResponse(
            status_code=200,  # 强制 HTTP 状态码为 200
            content={
                "code": code,
                "msg": msg,
                "data": data
            }
        )
