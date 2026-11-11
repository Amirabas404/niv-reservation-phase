from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from bots.customer.formatting import SPACE_NAMES, jalali_date_label

BTN_BOOK = "رزرو میز"
BTN_STATUS = "وضعیت رزرو من"
BTN_INFO = "ساعت کاری و آدرس"
BTN_SUPPORT = "پشتیبانی"
BTN_CANCEL = "انصراف"
BTN_END_CHAT = "پایان گفتگو"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_BOOK)],
            [KeyboardButton(text=BTN_STATUS), KeyboardButton(text=BTN_INFO)],
            [KeyboardButton(text=BTN_SUPPORT)],
        ],
        resize_keyboard=True,
    )


def cancel_only() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_CANCEL)]], resize_keyboard=True)


def contact_request() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="ارسال شماره من", request_contact=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _grid(buttons: list[InlineKeyboardButton], per_row: int) -> list[list[InlineKeyboardButton]]:
    return [buttons[i : i + per_row] for i in range(0, len(buttons), per_row)]


def dates_kb(days: list[date]) -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=jalali_date_label(d), callback_data=f"d:{d.isoformat()}") for d in days
    ]
    return InlineKeyboardMarkup(inline_keyboard=_grid(buttons, 2))


def times_kb(slots: list[str]) -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=s, callback_data=f"t:{s}") for s in slots]
    return InlineKeyboardMarkup(inline_keyboard=_grid(buttons, 4))


def party_kb() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=str(n), callback_data=f"p:{n}") for n in range(1, 11)]
    rows = _grid(buttons, 5)
    rows.append([InlineKeyboardButton(text="بیش از ۱۰ نفر", callback_data="p:more")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def spaces_kb() -> InlineKeyboardMarkup:
    buttons = [InlineKeyboardButton(text=name, callback_data=f"s:{code}") for code, name in SPACE_NAMES.items()]
    return InlineKeyboardMarkup(inline_keyboard=_grid(buttons, 2))


def designs_kb() -> InlineKeyboardMarkup:
    options = [
        ("بدون دیزاین", "none"),
        ("گل خشک و شمع", "dried_flower_candle"),
        ("استند بادکنک", "balloon_stand"),
        ("هر دو دیزاین", "both"),
    ]
    buttons = [InlineKeyboardButton(text=t, callback_data=f"g:{c}") for t, c in options]
    return InlineKeyboardMarkup(inline_keyboard=_grid(buttons, 2))


def cake_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(text="بله، کیک می‌آورم", callback_data="c:1"),
            InlineKeyboardButton(text="خیر", callback_data="c:0"),
        ]]
    )


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="ثبت درخواست ✅", callback_data="ok")],
            [InlineKeyboardButton(text="شروع دوباره", callback_data="restart")],
        ]
    )


def support_offer_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="اتصال به پشتیبانی", callback_data="support")]]
    )


def reservation_actions_kb(public_code: str, can_send_receipt: bool, can_cancel: bool) -> InlineKeyboardMarkup:
    row: list[InlineKeyboardButton] = []
    if can_send_receipt:
        row.append(InlineKeyboardButton(text="ارسال رسید", callback_data=f"rc:{public_code}"))
    if can_cancel:
        row.append(InlineKeyboardButton(text="درخواست لغو", callback_data=f"cx:{public_code}"))
    return InlineKeyboardMarkup(inline_keyboard=[row]) if row else InlineKeyboardMarkup(inline_keyboard=[])


def support_chat_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_END_CHAT)]], resize_keyboard=True)
