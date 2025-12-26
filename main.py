import logging

from dotenv import load_dotenv

from config.logger_config import init_logging_config

init_logging_config()
load_dotenv()

from contextlib import asynccontextmanager

from fastapi import FastAPI

from core.globals import init_globals
from init_main import init_main

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # [启动阶段]
    # 调用组装函数，初始化所有全局变量
    init_globals()
    yield
    # [关闭阶段]
    logging.info("资源释放...")


app = FastAPI(title='mulam助手API文档',
              summary='mulam助手的介绍1',
              description="""
              mulam助手的介绍2
              """,
              version='0.9.0',
              lifespan=lifespan)

init_main(app)
