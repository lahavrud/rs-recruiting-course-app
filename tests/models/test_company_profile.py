"""Tests for CompanyProfile model."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rs_shared.models import CompanyProfile


def _required_fields() -> dict:
    return {
        "name": "Test Company",
        "company_id": "123456789",
        "address": "רח׳ הדוגמה 1, תל אביב",
        "contact_email": "test-company@example.com",
        "contact_first_name": "ישראל",
        "contact_last_name": "ישראלי",
        "contact_mobile_phone": "0501234567",
    }


@pytest.mark.asyncio
async def test_company_profile_allows_null_user_id(session: AsyncSession):
    """Admin-created companies can exist without a linked user."""
    company = CompanyProfile(**_required_fields() | {"name": "Admin-Only Company"})
    session.add(company)
    await session.commit()
    await session.refresh(company)

    assert company.id is not None
    assert company.user_id is None
    assert company.name == "Admin-Only Company"
