from os import getenv

from sqlmodel import Session, create_engine

DATABASE_URL = getenv("DATABASE_URL", "sqlite:///./blunderfixer.db")
engine = create_engine(DATABASE_URL, echo=True)


def get_session():
    with Session(engine) as session:
        yield session
