from starlette.middleware.cors import CORSMiddleware

from config.logger_config import init_logging_config
from init_main import init_lifespan, init_main

init_logging_config()

from fastapi import FastAPI

app = FastAPI(title='沐蓝AI API文档',
              summary='简介',
              description="""
              具体描述
              """,
              version='0.9.0',
              lifespan=init_lifespan)

init_main(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    # allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", ],
    allow_headers=["*"],
)
