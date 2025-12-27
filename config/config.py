import os

from pydantic_settings import BaseSettings, SettingsConfigDict

from utils.abs_path import abs_path


class Settings(BaseSettings):
    # ============ 系统基础 ============
    # 如果 .env 里没有 SECRET_KEY，会报错（没有设置默认值），强制要求配置安全项
    # 如果想给默认值，写成 SECRET_KEY: str = "default_key"
    SECRET_KEY: str = 'default_key'

    # ============ MySQL ============
    # Pydantic 会自动读取环境变量中的 DB_HOST，读不到则使用默认值
    DB_HOST: str = '127.0.0.1'
    DB_PORT: int = 3306  # 自动将环境变量里的字符串 "3306" 转为 数字 3306
    DB_DATABASE: str = 'root'
    DB_USERNAME: str = 'root'
    DB_PASSWORD: str = 'root'

    # ============ Agent / 路径配置 ============
    # 这里可以直接调用你的函数作为默认值
    MODEL_PATH: str = abs_path("../models/bge-base-zh-v1.5")
    CHROMA_DB_PATH: str = abs_path("../asset/chroma_db")
    # 也可以在 .env 里覆盖这些路径，如果不覆盖就用上面的默认值
    GEN_TRY_TIMES: int = 3

    # LangSmith 配置
    # 注意：LangChain 官方推荐用 LANGCHAIN_API_KEY 这个名字，虽然 LANGSMITH_API_KEY 也能用
    DEEPSEEK_API_KEY: str = None
    LANGSMITH_API_KEY: str | None = None
    # 必须要有这个开关，否则光有 Key 也不生效
    LANGCHAIN_TRACING_V2: str = "true"
    LANGCHAIN_PROJECT: str = "mulam_assistant"  # 给你的项目起个名字

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

# ==========================================
# !!! 关键修复步骤 !!!
# 手动将配置注入回系统环境变量，供 LangChain 底层读取
# ==========================================
if settings.LANGSMITH_API_KEY:
    os.environ["DEEPSEEK_API_KEY"] = settings.DEEPSEEK_API_KEY
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
    os.environ["LANGCHAIN_TRACING_V2"] = settings.LANGCHAIN_TRACING_V2
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT

    # 可选：打印一下证明注入成功
    # print(f">>> LangSmith Tracing: Enabled (Project: {settings.LANGCHAIN_PROJECT})")
