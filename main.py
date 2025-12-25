from fastapi import FastAPI

from init_main import init_main
from router.user import user_router

app = FastAPI(title='mulam助手API文档',
              summary='mulam助手的介绍1',
              description="""
              mulam助手的介绍2
              """,
              version='0.9.0')

init_main(app)

app.include_router(user_router)
