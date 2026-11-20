from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.db import engine
from app.models import BrowserSession
from app.services.sessions import current


def transaction() -> Iterator[Session]:
    with Session(engine(), expire_on_commit=False) as db, db.begin():
        yield db


Database = Annotated[Session, Depends(transaction, scope="function")]


def authenticated(db: Database, request: Request) -> BrowserSession:
    return current(db, request)


Identity = Annotated[BrowserSession, Depends(authenticated, scope="function")]
