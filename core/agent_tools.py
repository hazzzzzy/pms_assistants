import logging
import time

from langchain_core.tools import tool
from sqlalchemy import text

from core.agent_context import AgentContext
from core.db import pms_mysql_engine

logger = logging.getLogger(__name__)


# class QueryResult:
#     code: int
#     result:
async def pms_query_mysql(query: str):
    """
    这是一个mysql数据库检索工具，执行SQL查询并返回结果，注意，只允许进行查询且使用此工具查询的表结构没有注释
    Args:
        query: SQL语句

    Returns:
        code: 状态码（0-成功，-1-失败，-2-不允许更改数据）
        result: 状态码为0时，返回查询结果；状态码不为0时，返回查询失败原因
    """
    # logger.info(f"[工具调用] 正在执行 SQL: {query}")
    try:
        query_header = ['SELECT', 'select', 'show', 'SHOW', 'DESCRIBE', 'describe']
        if not any([query.startswith(i) for i in query_header]):
            # if not query.startswith('SELECT') and not query.startswith('select'):
            return -2, f"执行失败: 不允许篡改数据"
        query_start_time = time.time()
        async with pms_mysql_engine.connect() as conn:
            result = await conn.execute(text(query))
            rows = result.fetchall()
            query_end_time = time.time()
            logger.info(f'查询耗时 {(query_end_time - query_start_time):4f}s')
            data = [dict(row._mapping) for row in rows]
        return 0, str(data)
    except Exception as e:
        logger.error(f'sql执行异常：{e}')
        return -1, f"执行失败: {str(e)}"


def pms_search_vector(ctx: AgentContext):
    @tool
    async def agent_search_vector(query: str, k: int = 5, schema_min_score: float = 2.0, qa_min_score: float = 0.5):
        """
        这是一个向量数据库检索工具,基于语义相似度检索表结构与预设问答sql向量数据库中的相关文档。
        仅供查询酒店内部相关数据时使用，例如经营数据、房态数据、酒店房间元数据等等
        当需要理解表结构、字段含义时，则必须使用此工具

        Args:
            query (str): 需要检索的查询文本（如用户的问题或关键词）。
            k (int): 返回的相关表结构与预设问答sql文档数量，默认值5
            schema_min_score (float): 表结构文档的分数阈值，分数越低表示越相关，默认值2.0。
            qa_min_score (float): 预设问答sql文档的分数阈值，分数越低表示越相关，默认值0.5。

        Returns:
            dict: {
                    'schema_result': List[Document],   # 表结构文档
                    'qa_result': List[Document]       # 预设问答sql文档
                    }
        """
        # logger.info(f"[工具调用] 正在检索向量数据库: {query}")
        vs_schema = ctx.vs_schema
        vs_qa = ctx.vs_qa
        if vs_schema is None or vs_qa is None:
            raise Exception('初始化未完成')

        # schema_search_result = vs_schema.similarity_search_with_score(query, k=k)
        schema_search_result = await vs_schema.amax_marginal_relevance_search(query=query, k=k, fetch_k=20,
                                                                              lambda_mult=0.5)
        # qa_query = f'为这个句子生成表示以用于检索相关文章：{query}'
        qa_search_result = await vs_qa.asimilarity_search_with_score(query, k=k)

        # 分数越低越相关
        schema_result, qa_result = '', ''
        for doc in schema_search_result:
            # if score < schema_min_score:
            # logger.info(doc.metadata['table_name'])
            doc = f'表名：{doc.metadata['table_name']}\n表中文名：{doc.metadata['table_zh_name']}\n表结构：{doc.metadata['table_structure']}\n'
            schema_result += doc
        for doc, score in qa_search_result:
            # logger.info([doc, score])
            if score <= qa_min_score:
                # logger.info(doc.metadata['table_name'])
                doc = f'该句sql的对应场景：{doc.page_content}\n备注：{doc.metadata['remark']}\nsql内容：{doc.metadata['a']}\n'
                qa_result += doc
        return {'qa_result': qa_result, 'schema_result': schema_result}

    return agent_search_vector
