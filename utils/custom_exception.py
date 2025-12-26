from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class BizException(Exception):
    def __init__(self, code: int, msg: str):
        self.code = code
        self.msg = msg


def register_exception_handler(app):
    # 1. 拦截业务手动抛出的 HTTPException
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=200,  # 强制 200
            content={
                # "code": exc.status_code,  # 保留业务状态码，但在 Body 里
                "code": -1,  # 保留业务状态码，但在 Body 里
                "msg": exc.detail,
                "data": None
            },
        )

    # 2. 拦截参数校验错误 (比如前端发了个字符串给 int 字段)
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        return JSONResponse(
            status_code=200,  # 强制 200
            content={
                # "code": 422,
                "code": -1,
                "msg": f"参数校验失败: {exc.errors()[0]['loc']}",  # 取第一条错误信息
                "data": None
            },
        )

    @app.exception_handler(BizException)
    async def biz_exception_handler(request: Request, exc: BizException):
        return JSONResponse(
            status_code=200,  # 即使报错，HTTP状态码也返回200（按你的需求）
            content={
                "code": -1,
                "msg": exc.msg,
                "data": None
            }
        )

    @app.exception_handler(Exception)
    async def biz_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=200,  # 即使报错，HTTP状态码也返回200（按你的需求）
            content={
                "code": -1,
                "msg": str(exc),
                "data": None
            }
        )
