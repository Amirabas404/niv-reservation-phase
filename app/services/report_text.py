"""Persian text for daily reports. Shared by the worker (nightly) and the management bot (on request)."""

from app.core.fa import fa, money

PAYMENT_LABELS = {
    "pending": "در انتظار پرداخت",
    "receipt_submitted": "رسید ارسال‌شده",
    "under_review": "در بررسی",
    "verified": "تأییدشده",
    "rejected": "ردشده",
}
SPACE_LABELS = {"hall": "سالن پایین", "roof_family": "روف‌گاردن خانوادگی",
                "roof_smoke_free": "روف‌گاردن فری اسموک", "vip": "VIP"}


def format_daily(report: dict) -> str:
    lines = [
        f"📊 گزارش روزانه NIV · {report['date_jalali']}",
        "",
        f"📝 درخواست‌های ثبت‌شده امروز: {fa(report['requested_today'])}",
        f"✅ تأییدشده: {fa(report['confirmed'])}",
        f"⏳ در انتظار: {fa(report['pending'])}",
        f"❌ ردشده: {fa(report['rejected'])}",
        f"🚫 لغوشده: {fa(report['cancelled'])}",
        f"👥 مجموع نفرات رزروها: {fa(report['guests_total'])}",
        "",
        "💳 وضعیت پرداخت‌ها:",
    ]
    if report["payments"]:
        for key, count in report["payments"].items():
            lines.append(f"• {PAYMENT_LABELS.get(key, key)}: {fa(count)}")
    else:
        lines.append("• موردی ثبت نشده")
    lines.append(f"• مبلغ تأییدشده: {money(report['verified_amount'])}")
    lines.append("")
    lines.append("🪑 فضاهای رزروشده:")
    if report["spaces"]:
        for code, s in report["spaces"].items():
            lines.append(f"• {SPACE_LABELS.get(code, s['name'])}: {fa(s['reservations'])} رزرو · {fa(s['guests'])} نفر")
    else:
        lines.append("• رزروی برای امروز نیست")
    t = report["tables"]
    lines.append("")
    lines.append(f"🍽 میزها: {fa(t['total'])} میز · مسدود: {fa(t['blocked'])} · ظرفیت تنظیم‌نشده: {fa(t['capacity_not_set'])}")
    return "\n".join(lines)
