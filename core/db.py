import logging
from contextlib import asynccontextmanager

from chromadb import Settings
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.config import settings

logger = logging.getLogger(__name__)


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


async def create_async_postgres_engine() -> AsyncPostgresSaver:
    POSTGRES_DB_URL = f"postgresql://{settings.POSTGRES_DB_USERNAME}:{settings.POSTGRES_DB_PASSWORD}@{settings.POSTGRES_DB_HOST}:{settings.POSTGRES_DB_PORT}/{settings.POSTGRES_DB_DATABASE}"
    connection_kwargs = {
        "autocommit": True,
        "prepare_threshold": 0,
        "sslmode": "disable"  # <--- 关键修复：禁用 SSL，解决报错
    }

    # 创建连接池
    pool = AsyncConnectionPool(
        conninfo=POSTGRES_DB_URL,
        max_size=20,
        kwargs=connection_kwargs,
        open=False)
    await pool.open()
    # 创建 Saver
    check_pointer = AsyncPostgresSaver(pool)

    # !!! 关键：首次启动自动建表 !!!
    await check_pointer.setup()
    return check_pointer


PMS_DB_URL = f"mysql+aiomysql://{settings.PMS_DB_USERNAME}:{settings.PMS_DB_PASSWORD}@{settings.PMS_DB_HOST}:{settings.PMS_DB_PORT}/{settings.PMS_DB_DATABASE}"
pms_mysql_engine = create_async_engine(
    PMS_DB_URL,
    pool_pre_ping=True,  # 关键：自动重连
    pool_size=10,  # 连接池大小
    max_overflow=20,  # 超出池大小后最多还能建多少个临时连接
    echo=False  # 是否打印所有 SQL (生产环境关掉)
)
logger.info(">>> 已加载 PMS MySQL Engine")

ASSISTANTS_DB_URL = f"mysql+aiomysql://{settings.ASSISTANTS_DB_USERNAME}:{settings.ASSISTANTS_DB_PASSWORD}@{settings.ASSISTANTS_DB_HOST}:{settings.ASSISTANTS_DB_PORT}/{settings.ASSISTANTS_DB_DATABASE}"
assistants_mysql_engine = create_async_engine(
    ASSISTANTS_DB_URL,
    pool_pre_ping=True,  # 关键：自动重连
    pool_size=10,  # 连接池大小
    max_overflow=20,  # 超出池大小后最多还能建多少个临时连接
    echo=False  # 是否打印所有 SQL (生产环境关掉)
)
logger.info(">>> 已加载 ASSISTANTS MySQL Engine")

async_session_maker = async_sessionmaker(
    bind=assistants_mysql_engine,  # 绑定上面的引擎
    class_=AsyncSession,  # 指定生成的 Session 类型是异步的
    expire_on_commit=False  # 【关键点】提交后不立刻过期
)
logger.info(">>> 已加载 SESSION MAKER")


# def create_async_mysql_engine() -> AsyncEngine:
#     engine = create_async_engine(
#         DB_URL,
#         pool_pre_ping=True,  # 关键：自动重连
#         pool_size=10,  # 连接池大小
#         max_overflow=20,  # 超出池大小后最多还能建多少个临时连接
#         echo=False  # 是否打印所有 SQL (生产环境关掉)
#     )
#     return engine


# def create_async_session_maker(engine):
#     # 3. 创建 Session 工厂 (Factory)
#     # 以前 Flask 里的 db.session 是个全局代理，自动帮你管理。
#     # 现在你需要自己造一个“生产 Session 的工厂”，每次请求都要从这里拿一个新的 Session。
#     AsyncSessionLocal = async_sessionmaker(
#         bind=engine,  # 绑定上面的引擎
#         class_=AsyncSession,  # 指定生成的 Session 类型是异步的
#         expire_on_commit=False  # 【关键点】提交后不立刻过期
#     )
#     return AsyncSessionLocal

@asynccontextmanager
async def db_session():
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            raise e
