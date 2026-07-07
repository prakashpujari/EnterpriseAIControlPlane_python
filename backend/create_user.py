import asyncio
import uuid
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.config.database import Base
from app.models.database import User
from app.config.settings import settings

# ------- EDIT THESE VALUES -------
EMAIL = "admin@example.com"
FULL_NAME = "Admin User"
ROLE = "support_engineer"          # support_engineer | mortgage_analyst | compliance_officer | product_owner
DEPARTMENT = "Support"
PASSWORD = "Admin123!"
# ---------------------------------

pwd_ctx = CryptContext(schemes=["sha256_crypt", "bcrypt"], deprecated="auto")
hashed_pw = pwd_ctx.hash(PASSWORD)

async def main():
    DATABASE_URL = settings.DATABASE_URL
    if DATABASE_URL.startswith("sqlite://"):
        DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://")
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        # Check if user already exists
        result = await session.execute(
            __import__("sqlalchemy").select(User).where(User.email == EMAIL)
        )
        existing = result.scalar_one_or_none()
        if existing:
            print(f"✅ User {EMAIL} already exists.")
            return

        new_user = User(
            id=str(uuid.uuid4()),
            email=EMAIL,
            full_name=FULL_NAME,
            role=ROLE,
            department=DEPARTMENT,
            password_hash=hashed_pw,
            is_active=True,
        )
        session.add(new_user)
        await session.commit()
        print(f"🎉 Created user {EMAIL} with password '{PASSWORD}'")

if __name__ == "__main__":
    asyncio.run(main())
