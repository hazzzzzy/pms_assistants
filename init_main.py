import logging
from contextlib import asynccontextmanager

from core.db import pms_mysql_engine
from core.globals import init_globals
from router import register_routers
from utils.custom_exception import register_exception_handler

logger = logging.getLogger(__name__)


def init_main(app):
    register_exception_handler(app)
    register_routers(app)


@asynccontextmanager
async def init_lifespan(app):
    await init_globals(app)
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
