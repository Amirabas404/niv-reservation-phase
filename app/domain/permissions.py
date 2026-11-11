"""Role-based access control. Enforced in the Backend; bots only hide buttons for convenience."""

from enum import StrEnum


class Role(StrEnum):
    MANAGER = "manager"
    SUPPORT = "support"


class Permission(StrEnum):
    VIEW_RESERVATIONS = "view_reservations"
    VIEW_AMOUNTS = "view_amounts"
    VIEW_PAYMENT_STATUS = "view_payment_status"
    VIEW_RECEIPTS = "view_receipts"
    CONFIRM_RESERVATION = "confirm_reservation"
    REJECT_RESERVATION = "reject_reservation"
    VERIFY_PAYMENT = "verify_payment"
    MANAGE_TABLES = "manage_tables"
    MANAGE_SETTINGS = "manage_settings"
    COORDINATE = "coordinate"
    VIEW_SUPPORT_REPORT = "view_support_report"
    VIEW_REPORTS = "view_reports"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.MANAGER: frozenset(Permission),
    Role.SUPPORT: frozenset(
        {
            Permission.VIEW_RESERVATIONS,
            Permission.VIEW_PAYMENT_STATUS,
            Permission.COORDINATE,
        }
    ),
}

# Fields removed from responses for roles without VIEW_AMOUNTS.
AMOUNT_FIELDS = frozenset({"total_amount", "amount_expected", "amount_verified", "price_snapshot", "refund_amount"})


def has_permission(role: Role | str, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[Role(role)]


def permissions_of(role: Role | str) -> list[str]:
    return sorted(p.value for p in ROLE_PERMISSIONS[Role(role)])


def redact_amounts(record: dict, role: Role | str) -> dict:
    if has_permission(role, Permission.VIEW_AMOUNTS):
        return record
    return {k: v for k, v in record.items() if k not in AMOUNT_FIELDS}
