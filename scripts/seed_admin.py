#!/usr/bin/env python3
"""Seed script to create an Admin user.

Usage:
    python scripts/seed_admin.py <email> <password>

Example:
    python scripts/seed_admin.py admin@example.com securepassword123
"""

import asyncio
import sys

from sqlalchemy import select

from rs_shared.core.infrastructure.database import async_session, init_db
from rs_shared.core.infrastructure.security import get_password_hash
from rs_shared.enums import UserRole
from rs_shared.models import User


async def create_admin_user(email: str, password: str) -> None:
    """Create an admin user in the database.

    Args:
        email: Admin user email
        password: Plain text password (will be hashed)
    """
    # Initialize database tables if they don't exist
    await init_db()

    async with async_session() as session:
        # Check if admin user already exists
        result = await session.execute(
            select(User).where(User.email == email)  # pyright: ignore[reportArgumentType]
        )
        existing_user = result.scalar_one_or_none()
        if existing_user:
            print(f"❌ User with email '{email}' already exists!")
            sys.exit(1)

        # Create admin user
        admin_user = User(
            email=email,
            hashed_password=get_password_hash(password),
            role=UserRole.ADMIN,
            is_active=True,  # Admin is active by default
        )
        session.add(admin_user)
        await session.commit()
        await session.refresh(admin_user)

        print("✅ Admin user created successfully!")
        print(f"   Email: {admin_user.email}")
        print(f"   Role: {admin_user.role.value}")
        print(f"   ID: {admin_user.id}")
        print(f"   Active: {admin_user.is_active}")


def main():
    """Main entry point for the seed script."""
    if len(sys.argv) != 3:
        print("Usage: python scripts/seed_admin.py <email> <password>")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]

    if not email or not password:
        print("❌ Email and password are required!")
        sys.exit(1)

    asyncio.run(create_admin_user(email, password))


if __name__ == "__main__":
    main()
