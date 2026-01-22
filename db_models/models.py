import datetime
from typing import Optional

from sqlalchemy import DateTime, String, Text, func, text, Integer
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.orm import Mapped, mapped_column

from db_models.base_model import Base


class ChatHistory(Base):
    __tablename__ = "chat_history"
    # 具体的业务字段
    question: Mapped[Optional[str]] = mapped_column(String(255, "utf8mb4_bin"))
    answer: Mapped[Optional[str]] = mapped_column(Text(collation="utf8mb4_bin"))
    # user_id: Mapped[Optional[str]] = mapped_column(String(255, "utf8mb4_bin"), nullable=True, default=None)
    file_name: Mapped[Optional[str]] = mapped_column(String(255, "utf8mb4_bin"), nullable=True, default=None)
    thread_id: Mapped[Optional[str]] = mapped_column(String(255, "utf8mb4_bin"), nullable=True, default=None)
    feedback: Mapped[int] = mapped_column(
        TINYINT, server_default=text("0"), default=0, comment="0-无反馈 1-赞 2-踩"
    )


class PresetQuestion(Base):
    __tablename__ = "preset_question"
    content: Mapped[Optional[str]] = mapped_column(String(255, "utf8mb4_bin"))

    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),  # 每次更新记录时自动刷新时间
    )


class UserThread(Base):
    __tablename__ = "user_thread"

    user_id: Mapped[Optional[int]] = mapped_column(Integer)
    hotel_id: Mapped[Optional[int]] = mapped_column(Integer)
    thread_id: Mapped[Optional[str]] = mapped_column(String(255, "utf8mb4_bin"), unique=True, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(255, "utf8mb4_bin"))
