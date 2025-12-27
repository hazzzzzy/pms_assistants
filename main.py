import logging

from config.logger_config import init_logging_config
from core.globals import init_globals
from router import register_routers
from utils.custom_exception import register_exception_handler

init_logging_config()

from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # [启动阶段]
    # 调用组装函数，初始化所有全局变量
    register_exception_handler(app)
    init_globals(app)
    register_routers(app)
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
