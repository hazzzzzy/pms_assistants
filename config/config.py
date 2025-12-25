import os

from utils.abs_path import abs_path

# ============ mysql ============
SECRET_KEY = os.getenv("SECRET_KEY")
# 数据库地址
DB_HOST = os.getenv("DB_HOST", '127.0.0.1')
# 数据库端口
DB_PORT = os.getenv("DB_PORT", 3306)
# 数据库名称
DB_DATABASE = os.getenv("DB_DATABASE", 'root')
# 数据库账号
DB_USERNAME = os.getenv("DB_USERNAME", 'root')
# 数据库密码
DB_PASSWORD = os.getenv("DB_PASSWORD", 'root')

#  ============ agent ============
MODEL_PATH = abs_path("../models/bge-base-zh-v1.5")
CHROMA_DB_PATH = abs_path("../asset/chroma_db")
# SQL_FILE_PATH = '../asset/tables_enriched.json'
# QA_FILE_PATH = '../asset/qa_sql.json'
GEN_TRY_TIMES = 3

DEEPSEEK_KEY = os.getenv("DEEPSEEK_KEY", 'sk-xxxxxx')
LANGSMITH_API_KEY = os.getenv("LANGSMITH_API_KEY", 'xxxxx')
