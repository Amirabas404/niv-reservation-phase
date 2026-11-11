from aiogram.fsm.state import State, StatesGroup


class ConfirmFlow(StatesGroup):
    picking = State()


class RejectFlow(StatesGroup):
    reason = State()
    payment_reason = State()


class CapacityFlow(StatesGroup):
    value = State()


class PriceFlow(StatesGroup):
    value = State()


class SupportFlow(StatesGroup):
    chatting = State()
