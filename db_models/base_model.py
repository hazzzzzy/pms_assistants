# 4. 定义模型基类 (Base)
# 对应以前 Flask 里的 db.Model
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
