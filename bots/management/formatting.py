"""Pure helpers for the management bot (no Telegram or DB imports)."""

from copy import deepcopy

from bots.customer.formatting import fa, money

STATUS_LABELS = {
    "pending_manager_approval": "منتظر تأیید مدیر",
    "awaiting_payment": "منتظر پرداخت",
    "receipt_submitted": "رسید ارسال شده",
    "confirmed": "تأیید شده",
    "rejected": "رد شده",
    "rejected_unpaid": "رد (عدم پرداخت)",
    "cancelled": "لغو شده",
}


def flatten_leaves(value: object, prefix: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], object]]:
    """Return (path, leaf) pairs for editable scalar settings, in stable order."""
    if isinstance(value, dict):
        out: list[tuple[tuple[str, ...], object]] = []
        for k in sorted(value):
            out.extend(flatten_leaves(value[k], prefix + (k,)))
        return out
    return [(prefix, value)]


def set_nested(value: dict, path: tuple[str, ...], new_value: object) -> dict:
    result = deepcopy(value)
    cursor = result
    for part in path[:-1]:
        cursor = cursor[part]
    cursor[path[-1]] = new_value
    return result


def parse_new_value(raw: str, current: object) -> object:
    """Convert user text to the same type as the current value. Raises ValueError on mismatch."""
    text = raw.strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    if isinstance(current, bool):
        raise ValueError("این مقدار از این ربات قابل ویرایش نیست.")
    if isinstance(current, int):
        return int(text.replace(",", ""))
    if isinstance(current, str):
        return text
    raise ValueError("این مقدار از این ربات قابل ویرایش نیست.")


def describe_reservation(item: dict, show_amounts: bool) -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from bots.customer.formatting import jalali_datetime_label

    start = datetime.fromisoformat(item["booking_start"])
    lines = [
        f"کد: {item['public_code']}",
        f"وضعیت: {STATUS_LABELS.get(item['status'], item['status'])}",
        f"📅 {jalali_datetime_label(start)}",
        f"👥 {fa(item['party_size'])} نفر · {item['space_name']}",
        f"👤 {item['customer_name']} · {fa(item['customer_phone'])}",
    ]
    if item.get("design") and item["design"] != "none":
        lines.append(f"🎨 دیزاین: {item['design']}")
    if item.get("payment_status"):
        lines.append(f"💳 پرداخت: {item['payment_status']}")
    if show_amounts and item.get("total_amount") is not None:
        lines.append(f"💰 مبلغ کل: {money(item['total_amount'])}")
    return "\n".join(lines)
