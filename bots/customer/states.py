from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    date = State()
    time = State()
    party = State()
    space = State()
    design = State()
    cake = State()
    name = State()
    phone = State()
    confirm = State()


class StatusStates(StatesGroup):
    phone = State()


class ReceiptStates(StatesGroup):
    waiting_photo = State()


class SupportStates(StatesGroup):
    chat = State()
