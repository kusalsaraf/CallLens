"""ORM model registry — import here to ensure models are registered on Base.metadata."""

from calllens.db.models.user import User

__all__ = ["User"]
