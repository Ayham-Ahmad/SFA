from api.db_session import engine, Base
from api.models import User
from passlib.context import CryptContext

# Create tables
Base.metadata.create_all(bind=engine)

print("Database initialized successfully.")
