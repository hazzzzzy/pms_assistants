import logging

from core.db import ChromaInstance, create_mysql_engine

logger = logging.getLogger(__name__)

# 1. 定义全局变量，初始为空
GlobalVsTableSchema = None
GlobalVsQa = None
GlobalGraph = None
GlobalSQLEngine = None


# 2. 定义初始化函数 (组装逻辑都在这)
def init_globals():
    global GlobalVsTableSchema, GlobalVsQa, GlobalGraph, GlobalSQLEngine

    if GlobalVsTableSchema is None or GlobalVsQa is None:
        chroma_instance = ChromaInstance()
        GlobalVsTableSchema = chroma_instance.load_vectorstore('table_structure')
        GlobalVsQa = chroma_instance.load_vectorstore('qa_sql')
        logging.info(">>> 已加载 Chroma 数据库")

    if GlobalSQLEngine is None:
        GlobalSQLEngine = create_mysql_engine()
        logging.info(">>> 已加载 MySQL Engine")

    # if GlobalGraph is None:
    #     agent_instance = AgentInstance()
    #     GlobalGraph = agent_instance.build()
    #     logging.info(">>> 已加载 Graph")
