from sqlalchemy.orm import Session
from api.db_session import SessionLocal, engine, Base
from api.models import User, UserRole
from api.auth_utils import get_password_hash

def create_admin():
    db = SessionLocal()
    try:
        # Check if admin exists
        user = db.query(User).filter(User.username == "admin").first()
        if user:
            print("Admin user already exists.")
            return

        # Create admin
        hashed_password = get_password_hash("admin123")
        admin_user = User(
            username="admin",
            password_hash=hashed_password,
            role=UserRole.ADMIN
        )
        db.add(admin_user)
        db.commit()
        print("Admin user created successfully. Username: admin, Password: admin123")
        
        # Create manager for testing
        manager_user = User(
            username="manager",
            password_hash=get_password_hash("manager123"),
            role=UserRole.MANAGER
        )
        db.add(manager_user)
        db.commit()
        print("Manager user created successfully. Username: manager, Password: manager123")
        
    except Exception as e:
        print(f"Error creating users: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_admin()
