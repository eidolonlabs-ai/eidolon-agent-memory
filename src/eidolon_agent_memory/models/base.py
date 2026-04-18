from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, MappedColumn, mapped_column
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy import DateTime
import uuid


class Base(DeclarativeBase):
    pass
