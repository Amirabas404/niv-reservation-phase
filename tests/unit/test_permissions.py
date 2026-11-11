from app.domain.permissions import Permission, Role, has_permission, redact_amounts


def test_manager_has_every_permission():
    for p in Permission:
        assert has_permission(Role.MANAGER, p)


def test_support_cannot_confirm_verify_or_see_receipts_or_amounts():
    assert not has_permission(Role.SUPPORT, Permission.CONFIRM_RESERVATION)
    assert not has_permission(Role.SUPPORT, Permission.VERIFY_PAYMENT)
    assert not has_permission(Role.SUPPORT, Permission.VIEW_RECEIPTS)
    assert not has_permission(Role.SUPPORT, Permission.VIEW_AMOUNTS)
    assert not has_permission(Role.SUPPORT, Permission.MANAGE_SETTINGS)


def test_support_can_view_reservations_and_payment_status():
    assert has_permission(Role.SUPPORT, Permission.VIEW_RESERVATIONS)
    assert has_permission(Role.SUPPORT, Permission.VIEW_PAYMENT_STATUS)


def test_redaction_removes_amounts_for_support_only():
    record = {"public_code": "NIV-1", "total_amount": 100, "amount_expected": 100, "status": "confirmed"}
    assert redact_amounts(record, Role.SUPPORT) == {"public_code": "NIV-1", "status": "confirmed"}
    assert redact_amounts(record, Role.MANAGER) == record
