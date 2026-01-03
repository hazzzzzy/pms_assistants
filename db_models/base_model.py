import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedAsDataclass, mapped_column


class Base(MappedAsDataclass, DeclarativeBase):
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, init=False)

    # 所有表都会自动拥有创建时间，且自动填充当前时间
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime,
        server_default=func.now(),  # 数据库层面的默认值 (NOW())
        default=func.now(),  # Python层面的默认值
        init=False
    )
