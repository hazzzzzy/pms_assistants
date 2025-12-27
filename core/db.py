from chromadb import Settings
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from sqlalchemy import create_engine, text

from config.config import settings


class ChromaInstance:
    def __init__(self):
        self.model = HuggingFaceEmbeddings(model_name=settings.MODEL_PATH)

    def load_vectorstore(self, collection_name):
        """为表结构数据创建向量存储"""
        # 加载JSON格式的表结构数据
        vectorstore = Chroma(
            embedding_function=self.model,
            persist_directory=settings.CHROMA_DB_PATH,
            collection_name=collection_name,
            client_settings=Settings(anonymized_telemetry=False)
        )
        return vectorstore

    @staticmethod
    def search_vector(vs, query, k=5, min_score: float = 2.0):
        search_result = vs.similarity_search_with_score(query, k=k)
        # print(search_result)
        # 分数越低越相关
        result = []
        for doc, score in search_result:
            if score < min_score:
                result.append(doc)
        return result


def create_mysql_engine():
    DB_URL = f"mysql+pymysql://{settings.DB_USERNAME}:{settings.DB_PASSWORD}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_DATABASE}"
    engine = create_engine(
        DB_URL,
        pool_pre_ping=True,  # 关键：自动重连
        pool_size=10,  # 连接池大小
        max_overflow=20,  # 超出池大小后最多还能建多少个临时连接
        echo=False  # 是否打印所有 SQL (生产环境关掉)
    )
    return engine


if __name__ == '__main__':
    question = '昨日餐券核销情况'
    # vs_qa = load_vectorstore('table_structure')
    # qa_search_result = search_vector(vs_qa, question)
    #
    # r = search_vector(vs_qa, question)
    # print(r)
    with create_mysql_engine().connect() as conn:
        rows = conn.execute(text(question)).fetchall()
        data = [dict(row._mapping) for row in rows]
        print(data)
