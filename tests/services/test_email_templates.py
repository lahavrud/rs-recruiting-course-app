"""Tests for HTML email template builders."""

from src.templates.email import build_approval_html, build_invite_html


def test_build_invite_html_contains_url():
    url = "https://example.com/register?token=abc123"
    html = build_invite_html(url)
    assert url in html
    assert "RS" in html
    assert 'dir="rtl"' in html


def test_build_invite_html_with_contact_name():
    html = build_invite_html("https://example.com", contact_name="ישראל")
    assert "ישראל" in html


def test_build_approval_html_contains_company_and_url():
    url = "https://example.com/activate?token=xyz"
    html = build_approval_html("חברת בדיקה", url)
    assert "חברת בדיקה" in html
    assert url in html
    assert 'dir="rtl"' in html
