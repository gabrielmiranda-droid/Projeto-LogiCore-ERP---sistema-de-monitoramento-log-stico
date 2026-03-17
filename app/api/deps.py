from sqlalchemy.orm import Session

from app.db.session import get_db


def db_dependency() -> Session:
    return next(get_db())
