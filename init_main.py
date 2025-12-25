from dotenv import load_dotenv
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


def init_main(app):
    load_dotenv()

    # 1. 拦截业务手动抛出的 HTTPException
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        return JSONResponse(
            status_code=200,  # 强制 200
            content={
                "code": exc.status_code,  # 保留业务状态码，但在 Body 里
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
                "code": 422,
                "msg": f"参数校验失败: {exc.errors()[0]['msg']}",  # 取第一条错误信息
                "data": str(exc)
            },
        )
