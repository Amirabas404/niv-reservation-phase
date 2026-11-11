from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font

COLUMNS = [
    ("تاریخ رزرو", "booking_date"),
    ("ساعت", "booking_time"),
    ("نام مشتری", "customer_name"),
    ("شماره موبایل", "customer_phone"),
    ("تعداد نفرات", "party_size"),
    ("فضا", "space"),
    ("میز", "tables"),
    ("دیزاین", "design"),
    ("هزینه رزرو فضا", "space_amount"),
    ("هزینه‌های پذیرایی", "catering_amount"),
    ("مبلغ کل", "total_amount"),
    ("مبلغ پرداخت‌شده", "paid_amount"),
    ("مبلغ برگشتی", "refund_amount"),
    ("وضعیت رزرو", "reservation_status"),
    ("وضعیت پرداخت", "payment_status"),
]

SUMMARY_LABELS = {
    "verified_payments_total": "مجموع پرداخت‌های تأییدشده",
    "refunds_total": "مجموع مبالغ برگشتی",
    "net_total": "خالص درآمد",
}


def build_monthly_workbook(rows: list[dict], summary: dict, title_ym: str) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "رزروها"
    ws.sheet_view.rightToLeft = True
    ws.append([header for header, _ in COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in rows:
        ws.append([row[key] for _, key in COLUMNS])
    ws.freeze_panes = "A2"
    for idx, (header, _) in enumerate(COLUMNS, start=1):
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = max(14, len(header) + 4)

    summary_ws = wb.create_sheet("خلاصه مالی")
    summary_ws.sheet_view.rightToLeft = True
    summary_ws.append([f"گزارش مالی ماه {title_ym}", ""])
    summary_ws["A1"].font = Font(bold=True)
    summary_ws.append(["شرح", "مبلغ (تومان)"])
    for key, label in SUMMARY_LABELS.items():
        summary_ws.append([label, summary.get(key, 0)])
    summary_ws.append([])
    summary_ws.append(["فقط پرداخت‌های تأییدشده و تراکنش‌های واقعی محاسبه شده‌اند."])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()
