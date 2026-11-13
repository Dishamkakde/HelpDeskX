from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, scoped_session
import os
from .config import Config

engine = create_engine(
    Config.SQLALCHEMY_DATABASE_URI,
    connect_args={"check_same_thread": False},
    echo=False
)

SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    from . import models
    Base.metadata.create_all(bind=engine)

