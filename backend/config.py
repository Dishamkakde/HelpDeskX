import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "helpdeskx-super-secret-key-2026")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'helpdeskx.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    TEAM_MAX_CAPACITY = 8
    DEBUG = True

