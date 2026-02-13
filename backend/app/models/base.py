"""SQLAlchemy 2.0+ declarative base for all VulnShop models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all ORM models.

    Uses SQLAlchemy 2.0 DeclarativeBase with Mapped[] type annotations
    for full type safety with async sessions.
    """

    pass
