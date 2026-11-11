from aiogram.types import InlineKeyboardButton as IB
from aiogram.types import InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


MENU_LABELS = {
    "درخواست‌های جدید", "پرداخت‌ها", "میزها", "قیمت‌ها", "گفتگوهای پشتیبانی", "گزارش پشتیبانی",
    "گزارش امروز", "اکسل ماه جاری",
}


def menu_for(role: str) -> ReplyKeyboardMarkup:
    support_row = [KeyboardButton(text="درخواست‌های جدید"), KeyboardButton(text="گفتگوهای پشتیبانی")]
    if role == "manager":
        rows = [
            support_row,
            [KeyboardButton(text="پرداخت‌ها"), KeyboardButton(text="میزها")],
            [KeyboardButton(text="قیمت‌ها"), KeyboardButton(text="گزارش پشتیبانی")],
            [KeyboardButton(text="گزارش امروز"), KeyboardButton(text="اکسل ماه جاری")],
        ]
    else:
        rows = [support_row]
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def ticket_actions(ticket: dict, my_id: int) -> InlineKeyboardMarkup | None:
    if ticket["status"] == "open":
        return InlineKeyboardMarkup(inline_keyboard=[[IB(text="پذیرش گفتگو", callback_data=f"tk:{ticket['id']}")]])
    if ticket["status"] == "claimed" and ticket["assigned_telegram_id"] == my_id:
        return InlineKeyboardMarkup(inline_keyboard=[[IB(text="ورود به گفتگو", callback_data=f"tv:{ticket['id']}")]])
    return None


def chat_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="پایان گفتگو")], [KeyboardButton(text="خروج از گفتگو")]],
        resize_keyboard=True,
    )


def request_actions(code: str, status: str, is_design: bool, can_manage: bool) -> InlineKeyboardMarkup | None:
    if not can_manage:
        return None
    rows: list[list[IB]] = []
    if status == "pending_manager_approval":
        rows.append([IB(text="تأیید و تخصیص میز", callback_data=f"ok:{code}"),
                     IB(text="رد", callback_data=f"no:{code}")])
    if status == "receipt_submitted":
        rows.append([IB(text="نمایش رسید", callback_data=f"rc:{code}")])
        rows.append([IB(text="تأیید پرداخت", callback_data=f"pay:{code}"),
                     IB(text="رد پرداخت", callback_data=f"payno:{code}")])
    return InlineKeyboardMarkup(inline_keyboard=rows) if rows else None


def tables_picker(tables: list[dict], selected: set[int]) -> InlineKeyboardMarkup:
    rows: list[list[IB]] = []
    row: list[IB] = []
    for t in tables:
        mark = "✅ " if t["id"] in selected else ""
        cap = t["capacity"] if t["capacity"] is not None else "—"
        label = f"{mark}{t['number']} ({cap})"
        if t["is_blocked"]:
            label += " ⛔"
        row.append(IB(text=label, callback_data=f"tp:{t['id']}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([IB(text="تأیید تخصیص", callback_data="tpdone"), IB(text="انصراف", callback_data="tpcancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def table_actions(table_id: int, is_blocked: bool) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        IB(text="تنظیم ظرفیت", callback_data=f"tc:{table_id}"),
        IB(text="باز کردن" if is_blocked else "مسدود کردن", callback_data=f"tx:{table_id}"),
    ]])
