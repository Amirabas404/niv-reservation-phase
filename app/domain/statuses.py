from enum import StrEnum

from app.domain.errors import InvalidTransitionError


class ReservationStatus(StrEnum):
    PENDING_MANAGER = "pending_manager_approval"
    AWAITING_PAYMENT = "awaiting_payment"
    RECEIPT_SUBMITTED = "receipt_submitted"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"
    REJECTED_UNPAID = "rejected_unpaid"
    CANCELLED = "cancelled"


class PaymentStatus(StrEnum):
    PENDING = "pending"
    RECEIPT_SUBMITTED = "receipt_submitted"
    UNDER_REVIEW = "under_review"
    VERIFIED = "verified"
    REJECTED = "rejected"


RS = ReservationStatus

ALLOWED_TRANSITIONS: dict[ReservationStatus, frozenset[ReservationStatus]] = {
    RS.PENDING_MANAGER: frozenset({RS.CONFIRMED, RS.REJECTED, RS.CANCELLED}),
    RS.AWAITING_PAYMENT: frozenset({RS.RECEIPT_SUBMITTED, RS.REJECTED_UNPAID, RS.CANCELLED}),
    RS.RECEIPT_SUBMITTED: frozenset({RS.CONFIRMED, RS.REJECTED, RS.CANCELLED, RS.AWAITING_PAYMENT}),
    RS.CONFIRMED: frozenset({RS.CANCELLED}),
    RS.REJECTED: frozenset(),
    RS.REJECTED_UNPAID: frozenset(),
    RS.CANCELLED: frozenset(),
}


def assert_transition(current: str, target: ReservationStatus) -> None:
    current_status = ReservationStatus(current)
    if target not in ALLOWED_TRANSITIONS[current_status]:
        raise InvalidTransitionError(
            f"تغییر وضعیت از «{current_status.value}» به «{target.value}» مجاز نیست."
        )
