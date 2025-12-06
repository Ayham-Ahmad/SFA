from api.database import SessionLocal, engine, Base
from api.models import User
from api.auth import get_password_hash

# Create tables
Base.metadata.create_all(bind=engine)

db = SessionLocal()

username = "manager"
password = "password123"

# Check if exists
user = db.query(User).filter(User.username == username).first()
if not user:
    print(f"Creating user {username}...")
    user = User(
        username=username,
        password_hash=get_password_hash(password),
        role="manager"
    )
    db.add(user)
    db.commit()
    print("User created.")
else:
    print("User already exists.")
    # Reset password just in case
    user.password_hash = get_password_hash(password)
    db.commit()
    print("Password reset.")

db.close()
