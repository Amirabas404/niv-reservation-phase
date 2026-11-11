from io import BytesIO

from openpyxl import load_workbook

from app.integrations.excel import COLUMNS, build_monthly_workbook


def test_workbook_has_required_columns_and_rtl_sheets():
    row = {key: 0 for _, key in COLUMNS}
    row.update({"customer_name": "علی", "reservation_status": "confirmed"})
    data = build_monthly_workbook([row], {"verified_payments_total": 10, "refunds_total": 5, "net_total": 5}, "2026-11")
    wb = load_workbook(BytesIO(data))
    ws = wb["رزروها"]
    headers = [c.value for c in ws[1]]
    assert headers == [h for h, _ in COLUMNS]
    assert ws.sheet_view.rightToLeft is True
    assert ws.max_row == 2
    summary = wb["خلاصه مالی"]
    values = {summary.cell(row=r, column=1).value: summary.cell(row=r, column=2).value for r in range(3, 6)}
    assert values["خالص درآمد"] == 5
