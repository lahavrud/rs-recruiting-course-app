import pytest

from rs_shared.core.utils import mask_email


@pytest.mark.parametrize(
    "input,expected",
    [
        ("john.doe@example.com", "jo***@example.com"),
        ("ab@example.com", "ab***@example.com"),
        ("a@example.com", "a***@example.com"),
        ("", "***"),
        ("notanemail", "***"),
    ],
)
def test_mask_email_single(input, expected):
    assert mask_email(input) == expected


def test_mask_email_list():
    result = mask_email(["alice@example.com", "bob@example.com"])
    assert result == "al***@example.com, bo***@example.com"


def test_mask_email_empty_list():
    assert mask_email([]) == ""
