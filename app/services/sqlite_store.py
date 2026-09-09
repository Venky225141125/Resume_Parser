from pathlib import Path

from sqlalchemy import String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

from app.schemas.candidate import ParseResponse
from app.services.store import ResultStore


class Base(DeclarativeBase):
    pass


class ParseRunRow(Base):
    __tablename__ = "parse_runs"

    document_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    payload: Mapped[str] = mapped_column(Text)


class SqliteResultStore(ResultStore):
    def __init__(self, database_url: str) -> None:
        if database_url.startswith("sqlite:///./"):
            Path("data").mkdir(exist_ok=True)
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self._engine = create_engine(database_url, connect_args=connect_args)
        Base.metadata.create_all(self._engine)
        self._session = sessionmaker(bind=self._engine)

    def save(self, result: ParseResponse) -> None:
        payload = result.model_dump_json()
        with self._session() as session:
            row = session.get(ParseRunRow, result.document_id)
            if row is None:
                session.add(ParseRunRow(document_id=result.document_id, payload=payload))
            else:
                row.payload = payload
            session.commit()

    def get(self, document_id: str) -> ParseResponse | None:
        with self._session() as session:
            row = session.get(ParseRunRow, document_id)
            if row is None:
                return None
            return ParseResponse.model_validate_json(row.payload)
