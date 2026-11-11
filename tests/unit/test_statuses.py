import pytest

from app.domain.errors import InvalidTransitionError
from app.domain.statuses import ReservationStatus as RS
from app.domain.statuses import assert_transition


def test_pending_can_be_confirmed():
    assert_transition(RS.PENDING_MANAGER.value, RS.CONFIRMED)


def test_awaiting_payment_cannot_be_confirmed_directly():
    with pytest.raises(InvalidTransitionError):
        assert_transition(RS.AWAITING_PAYMENT.value, RS.CONFIRMED)


def test_terminal_states_have_no_exit():
    for terminal in (RS.REJECTED, RS.REJECTED_UNPAID, RS.CANCELLED):
        with pytest.raises(InvalidTransitionError):
            assert_transition(terminal.value, RS.CONFIRMED)
