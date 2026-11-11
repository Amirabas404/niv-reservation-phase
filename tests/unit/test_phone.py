import pytest

from app.core.phone import normalize_phone
from app.domain.errors import InvalidPhoneError


@pytest.mark.parametrize(
    "raw",
    ["09382123520", "0938 212 3520", "+989382123520", "00989382123520", "9382123520", "۰۹۳۸۲۱۲۳۵۲۰"],
)
def test_valid_variants_normalize(raw):
    assert normalize_phone(raw) == "09382123520"


@pytest.mark.parametrize("raw", ["0218123456", "09123", "abc", ""])
def test_invalid_numbers_are_rejected(raw):
    with pytest.raises(InvalidPhoneError):
        normalize_phone(raw)
