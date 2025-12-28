import logging

from fastapi import FastAPI

from core.agent_context import AgentContext
from core.agent_instance import AgentInstance
from core.db import ChromaInstance, create_async_mysql_engine

logger = logging.getLogger(__name__)


def init_globals(app: FastAPI):
    chroma_instance = ChromaInstance()
    app.state.vs_schema = chroma_instance.load_vectorstore('table_structure')
    app.state.vs_qa = chroma_instance.load_vectorstore('qa_sql')
    logging.info(">>> 已加载 Chroma 数据库")

    app.state.mysql_engine = create_async_mysql_engine()
    logging.info(">>> 已加载 MySQL Engine")

    ctx = AgentContext(app, include_graph=False)
    app.state.graph = AgentInstance().build(ctx)
    logging.info(">>> 已加载 Graph")
