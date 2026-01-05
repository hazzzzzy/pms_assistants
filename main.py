import logging

from starlette.middleware.cors import CORSMiddleware

from config.logger_config import init_logging_config
from core.db import pms_mysql_engine
from core.globals import init_globals
from router import register_routers
from utils.custom_exception import register_exception_handler

init_logging_config()

from contextlib import asynccontextmanager

from fastapi import FastAPI

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    register_exception_handler(app)
    await init_globals(app)

    register_routers(app)
    yield
    logger.info(">>> 正在关闭 ASYNC MYSQL ENGINE...")
    await pms_mysql_engine.dispose()

    # 1. 关闭 Postgres 连接池 (修复卡死问题的关键)
    pg_saver = getattr(app.state, "postgres_engine", None)
    if pg_saver:
        # 尝试获取我们刚才绑定的 pool_ref
        pool = getattr(pg_saver, "pool_ref", None)

        # 如果找不到 pool_ref，尝试找 LangGraph 默认的 .conn (双重保险)
        if not pool and hasattr(pg_saver, "conn"):
            pool = pg_saver.conn

        if pool:
            logger.info(">>> 正在关闭 Postgres 连接池...")
            await pool.close()  # <--- 这句执行完，进程就能退出了
            logger.info(">>> Postgres 连接池已关闭")
        logger.info(">>> Postgres 连接已关闭")


app = FastAPI(title='mulam助手API文档',
              summary='mulam助手的介绍1',
              description="""
              mulam助手的介绍2
              """,
              version='0.9.0',
              lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    # allow_credentials=True,
    allow_methods=["GET", "POST", "OPTION", ],
    allow_headers=["*"],
)
