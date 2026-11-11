import pytest

from app.domain.errors import DomainError
from app.domain.permissions import Permission, Role, has_permission
from app.services.support_service import MAX_TEXT, _clean


def test_support_role_can_coordinate_but_not_see_report():
    assert has_permission(Role.SUPPORT, Permission.COORDINATE)
    assert not has_permission(Role.SUPPORT, Permission.VIEW_SUPPORT_REPORT)


def test_manager_can_see_support_report():
    assert has_permission(Role.MANAGER, Permission.VIEW_SUPPORT_REPORT)


def test_empty_message_is_rejected():
    with pytest.raises(DomainError):
        _clean("   ")


def test_long_message_is_rejected():
    with pytest.raises(DomainError):
        _clean("x" * (MAX_TEXT + 1))


def test_message_is_trimmed():
    assert _clean("  سلام  ") == "سلام"
