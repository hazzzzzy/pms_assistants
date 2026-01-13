import logging

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


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
        # 以此来获取更人性化的错误提示
        # errors 格式通常是 [{'loc': ('body', 'price'), 'msg': 'field required', 'type': 'value_error.missing'}]
        try:
            detail = exc.errors()[0]
            # 拼接错误字段和错误信息，例如: "参数校验失败: body.price field required"
            msg = f"参数校验失败: {'.'.join(str(x) for x in detail.get('loc', []))} {detail.get('msg', '')}"
        except (IndexError, KeyError, TypeError):
            msg = "参数校验失败"

        return JSONResponse(
            status_code=200,
            content={
                "code": -1,
                "msg": msg,
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
        logger.error(str(exc))
        return JSONResponse(
            status_code=200,  # 即使报错，HTTP状态码也返回200（按你的需求）
            content={
                "code": -1,
                "msg": str(exc),
                "data": None
            }
        )
