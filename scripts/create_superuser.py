import asyncio
import sys
import os

# Add backend directory to python path
sys.path.append(os.path.join(os.path.dirname(__file__), "../backend"))

from app.db.session import SessionLocal
from app.models.user import User, UserTier
from app.core.security import get_password_hash
from sqlalchemy.future import select

async def create_superuser():
    async with SessionLocal() as db:
        email = "admin@example.com"
        password = "adminpassword"
        
        # Check if user exists
        result = await db.execute(select(User).where(User.email == email))
        existing_user = result.scalars().first()
        
        if existing_user:
            print(f"User {email} already exists.")
            return

        user = User(
            email=email,
            password_hash=get_password_hash(password),
            full_name="Super Admin",
            tier=UserTier.ENTERPRISE
        )
        db.add(user)
        await db.commit()
        print(f"Superuser {email} created successfully.")

if __name__ == "__main__":
    asyncio.run(create_superuser())
