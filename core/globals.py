import logging

from fastapi import FastAPI

from core.agent_context import AgentContext
from core.agent_instance import AgentInstance
from core.db import ChromaInstance, create_async_mysql_engine, create_async_postgres_engine, create_async_session_maker

logger = logging.getLogger(__name__)


async def init_globals(app: FastAPI):
    chroma_instance = ChromaInstance()
    app.state.vs_schema = chroma_instance.load_vectorstore('table_structure')
    app.state.vs_qa = chroma_instance.load_vectorstore('qa_sql')
    logging.info(">>> 已加载 Chroma 数据库")

    async_mysql_engine = create_async_mysql_engine()
    app.state.mysql_engine = async_mysql_engine
    logging.info(">>> 已加载 MySQL Engine")

    async_session_maker = create_async_session_maker(async_mysql_engine)
    app.state.async_session_maker = async_session_maker
    logging.info(">>> 已加载 SESSION MAKER")

    checkpointer = await create_async_postgres_engine()
    app.state.postgres_engine = checkpointer
    logging.info(">>> 已加载 POSTGRES CHECKPOINT SAVER")

    ctx = AgentContext(app, include_graph=False)
    app.state.graph = AgentInstance().build(ctx, checkpointer)
    logging.info(">>> 已加载 Graph")
