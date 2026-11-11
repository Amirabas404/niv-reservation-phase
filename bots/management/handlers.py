import logging
import os
from datetime import datetime
from io import BytesIO
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bots.management import keyboards as kb
from bots.management.backend import AdminBackend, AdminBackendError
from bots.management.formatting import describe_reservation, flatten_leaves, parse_new_value, set_nested
from app.services.report_text import format_daily
from bots.customer.formatting import fa
from bots.management.states import CapacityFlow, ConfirmFlow, PriceFlow, RejectFlow, SupportFlow

log = logging.getLogger(__name__)
router = Router(name="management")

PENDING = ["pending_manager_approval", "receipt_submitted"]
SETTING_KEYS = ["pricing", "rules"]


async def _me(message_or_cb, backend: AdminBackend) -> dict | None:
    actor = message_or_cb.from_user.id
    try:
        return await backend.me(actor)
    except AdminBackendError:
        return None


async def _need_manager(message: Message, backend: AdminBackend) -> dict | None:
    me = await _me(message, backend)
    if not me or me["role"] != "manager":
        await message.answer("این بخش فقط برای مدیر است.")
        return None
    return me


@router.message(CommandStart())
async def start(message: Message, backend: AdminBackend) -> None:
    me = await _me(message, backend)
    if not me:
        await message.answer("شما به این ربات دسترسی ندارید.")
        return
    await message.answer(f"سلام {me['display_name']} 👋", reply_markup=kb.menu_for(me["role"]))


# ---------- requests ----------

@router.message(F.text == "درخواست‌های جدید")
async def pending(message: Message, backend: AdminBackend) -> None:
    me = await _me(message, backend)
    if not me:
        await message.answer("دسترسی ندارید.")
        return
    try:
        items = await backend.reservations(message.from_user.id, PENDING)
    except AdminBackendError as exc:
        await message.answer(exc.message)
        return
    if not items:
        await message.answer("درخواست در انتظاری وجود ندارد ✅")
        return
    can_manage = me["role"] == "manager"
    for item in items:
        await message.answer(
            describe_reservation(item, show_amounts=can_manage),
            reply_markup=kb.request_actions(item["public_code"], item["status"], item["design"] != "none", can_manage),
        )


@router.callback_query(F.data.startswith("ok:"))
async def confirm_start(cb: CallbackQuery, state: FSMContext, backend: AdminBackend) -> None:
    code = cb.data.split(":", 1)[1]
    items = await backend.reservations(cb.from_user.id, ["pending_manager_approval"])
    item = next((i for i in items if i["public_code"] == code), None)
    if item is None:
        await cb.answer("این درخواست دیگر در انتظار نیست.", show_alert=True)
        return
    tables = await backend.tables(cb.from_user.id, item["space_code"])
    await state.set_state(ConfirmFlow.picking)
    await state.update_data(code=code, selected=[], party=item["party_size"], space=item["space_code"])
    await cb.message.answer(
        f"میز(های) {code} را انتخاب کنید (عدد داخل پرانتز ظرفیت است).\n"
        f"تعداد نفرات: {item['party_size']}",
        reply_markup=kb.tables_picker(tables, set()),
    )
    await cb.answer()


@router.callback_query(ConfirmFlow.picking, F.data.startswith("tp:"))
async def toggle_table(cb: CallbackQuery, state: FSMContext, backend: AdminBackend) -> None:
    table_id = int(cb.data.split(":", 1)[1])
    data = await state.get_data()
    selected = set(data["selected"])
    selected.symmetric_difference_update({table_id})
    await state.update_data(selected=sorted(selected))
    tables = await backend.tables(cb.from_user.id, data["space"])
    await cb.message.edit_reply_markup(reply_markup=kb.tables_picker(tables, selected))
    await cb.answer()


@router.callback_query(ConfirmFlow.picking, F.data == "tpdone")
async def confirm_done(cb: CallbackQuery, state: FSMContext, backend: AdminBackend) -> None:
    data = await state.get_data()
    if not data["selected"]:
        await cb.answer("حداقل یک میز انتخاب کنید.", show_alert=True)
        return
    try:
        await backend.confirm(cb.from_user.id, data["code"], data["selected"])
    except AdminBackendError as exc:
        await cb.answer(exc.message, show_alert=True)
        return
    await state.clear()
    await cb.message.answer(f"رزرو {data['code']} تأیید شد ✅")
    await cb.answer()


@router.callback_query(ConfirmFlow.picking, F.data == "tpcancel")
async def confirm_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.answer("تخصیص میز لغو شد.")
    await cb.answer()


@router.callback_query(F.data.startswith("no:"))
async def reject_start(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RejectFlow.reason)
    await state.update_data(code=cb.data.split(":", 1)[1], mode="reservation")
    await cb.message.answer("دلیل رد درخواست را بنویسید:")
    await cb.answer()


@router.callback_query(F.data.startswith("payno:"))
async def payment_reject_start(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(RejectFlow.reason)
    await state.update_data(code=cb.data.split(":", 1)[1], mode="payment")
    await cb.message.answer("دلیل رد پرداخت را بنویسید:")
    await cb.answer()


@router.message(RejectFlow.reason, F.text)
async def reject_reason(message: Message, state: FSMContext, backend: AdminBackend) -> None:
    data = await state.get_data()
    try:
        if data["mode"] == "payment":
            await backend.reject_payment(message.from_user.id, data["code"], message.text.strip())
        else:
            await backend.reject(message.from_user.id, data["code"], message.text.strip())
    except AdminBackendError as exc:
        await message.answer(exc.message)
        return
    await state.clear()
    await message.answer("ثبت شد ✅")


# ---------- payments ----------

@router.message(F.text == "پرداخت‌ها")
async def payments(message: Message, backend: AdminBackend) -> None:
    me = await _need_manager(message, backend)
    if not me:
        return
    items = await backend.reservations(message.from_user.id, ["receipt_submitted"])
    if not items:
        await message.answer("رسید در انتظار بررسی وجود ندارد ✅")
        return
    for item in items:
        await message.answer(describe_reservation(item, True),
                             reply_markup=kb.request_actions(item["public_code"], item["status"], True, True))


@router.callback_query(F.data.startswith("rc:"))
async def show_receipt(cb: CallbackQuery, backend: AdminBackend) -> None:
    code = cb.data.split(":", 1)[1]
    try:
        data = await backend.receipt(cb.from_user.id, code)
    except AdminBackendError as exc:
        await cb.answer(exc.message, show_alert=True)
        return
    await cb.message.answer_photo(BufferedInputFile(data, filename=f"{code}.jpg"), caption=f"رسید {code}")
    await cb.answer()


@router.callback_query(F.data.startswith("pay:"))
async def verify_payment(cb: CallbackQuery, backend: AdminBackend) -> None:
    code = cb.data.split(":", 1)[1]
    items = await backend.reservations(cb.from_user.id, ["receipt_submitted"])
    item = next((i for i in items if i["public_code"] == code), None)
    if item is None or item.get("amount_expected") is None:
        await cb.answer("اطلاعات پرداخت یافت نشد.", show_alert=True)
        return
    try:
        await backend.verify_payment(cb.from_user.id, code, item["amount_expected"])
    except AdminBackendError as exc:
        await cb.answer(exc.message, show_alert=True)
        return
    await cb.message.answer(f"پرداخت {code} تأیید شد ✅ حالا می‌توانید میز تخصیص دهید.")
    await cb.answer()


# ---------- tables ----------

@router.message(F.text == "میزها")
async def tables(message: Message, backend: AdminBackend) -> None:
    me = await _need_manager(message, backend)
    if not me:
        return
    rows = await backend.tables(message.from_user.id)
    for t in rows:
        cap = t["capacity"] if t["capacity"] is not None else "تنظیم نشده"
        state_text = "⛔ مسدود" if t["is_blocked"] else "فعال"
        await message.answer(
            f"{t['space_name']} · میز {t['number']}\nظرفیت: {cap} · {state_text}",
            reply_markup=kb.table_actions(t["id"], t["is_blocked"]),
        )


@router.callback_query(F.data.startswith("tx:"))
async def toggle_block(cb: CallbackQuery, backend: AdminBackend) -> None:
    table_id = int(cb.data.split(":", 1)[1])
    rows = await backend.tables(cb.from_user.id)
    t = next(r for r in rows if r["id"] == table_id)
    try:
        await backend.update_table(cb.from_user.id, table_id, is_blocked=not t["is_blocked"])
    except AdminBackendError as exc:
        await cb.answer(exc.message, show_alert=True)
        return
    await cb.answer("به‌روزرسانی شد ✅")


@router.callback_query(F.data.startswith("tc:"))
async def capacity_start(cb: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(CapacityFlow.value)
    await state.update_data(table_id=int(cb.data.split(":", 1)[1]))
    await cb.message.answer("ظرفیت جدید میز را به عدد وارد کنید (۱ تا ۳۰):")
    await cb.answer()


@router.message(CapacityFlow.value, F.text)
async def capacity_value(message: Message, state: FSMContext, backend: AdminBackend) -> None:
    try:
        capacity = int(message.text.strip())
    except ValueError:
        await message.answer("لطفاً فقط عدد وارد کنید.")
        return
    data = await state.get_data()
    try:
        await backend.update_table(message.from_user.id, data["table_id"], capacity=capacity)
    except AdminBackendError as exc:
        await message.answer(exc.message)
        return
    await state.clear()
    await message.answer("ظرفیت ذخیره شد ✅")


# ---------- prices & rules ----------

@router.message(F.text == "قیمت‌ها")
async def prices(message: Message, backend: AdminBackend) -> None:
    me = await _need_manager(message, backend)
    if not me:
        return
    from aiogram.types import InlineKeyboardButton as IB
    from aiogram.types import InlineKeyboardMarkup

    rows = []
    for key in SETTING_KEYS:
        rows.append([IB(text=f"ویرایش {key}", callback_data=f"sk:{key}")])
    await message.answer("کدام بخش را ویرایش می‌کنید؟", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


@router.callback_query(F.data.startswith("sk:"))
async def price_fields(cb: CallbackQuery, state: FSMContext, backend: AdminBackend) -> None:
    from aiogram.types import InlineKeyboardButton as IB
    from aiogram.types import InlineKeyboardMarkup

    key = cb.data.split(":", 1)[1]
    setting = await backend.get_setting(cb.from_user.id, key)
    fields = flatten_leaves(setting["value"])
    await state.update_data(setting_key=key, version=setting["version"], fields=[list(p) for p, _ in fields])
    buttons = []
    for idx, (path, value) in enumerate(fields):
        buttons.append([IB(text=f"{'.'.join(path)} = {value}", callback_data=f"sf:{idx}")])
    await cb.message.answer("کدام مقدار را تغییر می‌دهید؟", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons[:40]))
    await cb.answer()


@router.callback_query(F.data.startswith("sf:"))
async def price_field_pick(cb: CallbackQuery, state: FSMContext) -> None:
    idx = int(cb.data.split(":", 1)[1])
    data = await state.get_data()
    await state.set_state(PriceFlow.value)
    await state.update_data(field_path=data["fields"][idx])
    await cb.message.answer("مقدار جدید را وارد کنید:")
    await cb.answer()


@router.message(PriceFlow.value, F.text)
async def price_value(message: Message, state: FSMContext, backend: AdminBackend) -> None:
    data = await state.get_data()
    key = data["setting_key"]
    path = tuple(data["field_path"])
    current_setting = await backend.get_setting(message.from_user.id, key)
    current = current_setting["value"]
    cursor = current
    for part in path:
        cursor = cursor[part]
    try:
        new_value = parse_new_value(message.text, cursor)
    except ValueError as exc:
        await message.answer(str(exc))
        return
    updated = set_nested(current, path, new_value)
    try:
        await backend.put_setting(message.from_user.id, key, updated, current_setting["version"])
    except AdminBackendError as exc:
        await message.answer(exc.message)
        return
    await state.clear()
    await message.answer("ذخیره شد ✅ از این لحظه برای رزروهای جدید اعمال می‌شود.")


# ---------- support conversations ----------

def _ticket_text(t: dict) -> str:
    last = t.get("last_customer_message")
    preview = last["text"][:120] if last else "—"
    owner = f"پذیرفته: {t['assigned_name']}" if t["status"] == "claimed" else "در انتظار پذیرش"
    return (f"گفتگو #{t['id']} · {owner}\n"
            f"موضوع: {t['reason']}\n"
            f"آخرین پیام مشتری: {preview}")


@router.message(F.text == "گفتگوهای پشتیبانی")
async def support_queue(message: Message, backend: AdminBackend) -> None:
    me = await _me(message, backend)
    if not me:
        await message.answer("دسترسی ندارید.")
        return
    items = await backend.tickets(message.from_user.id, ["open", "claimed"])
    if not items:
        await message.answer("گفتگوی فعالی وجود ندارد ✅")
        return
    for t in items:
        await message.answer(_ticket_text(t), reply_markup=kb.ticket_actions(t, message.from_user.id))


async def _enter_chat(cb_or_msg_user: int, message: Message, state: FSMContext, backend: AdminBackend, ticket_id: int) -> None:
    history = await backend.ticket_history(cb_or_msg_user, ticket_id)
    lines = [f"— گفتگو #{ticket_id} —"]
    for m in history[-8:]:
        who = {"customer": "مشتری", "staff": "پشتیبان", "system": "سیستم"}.get(m["sender"], m["sender"])
        lines.append(f"{who}: {m['text']}")
    await state.set_state(SupportFlow.chatting)
    await state.update_data(ticket_id=ticket_id)
    await message.answer("\n".join(lines), reply_markup=kb.chat_kb())


@router.callback_query(F.data.startswith("tk:"))
async def claim_ticket(cb: CallbackQuery, state: FSMContext, backend: AdminBackend) -> None:
    ticket_id = int(cb.data.split(":", 1)[1])
    try:
        await backend.claim_ticket(cb.from_user.id, ticket_id)
    except AdminBackendError as exc:
        await cb.answer(exc.message, show_alert=True)
        return
    await cb.answer("گفتگو به شما واگذار شد ✅")
    await _enter_chat(cb.from_user.id, cb.message, state, backend, ticket_id)


@router.callback_query(F.data.startswith("tv:"))
async def enter_ticket(cb: CallbackQuery, state: FSMContext, backend: AdminBackend) -> None:
    ticket_id = int(cb.data.split(":", 1)[1])
    await cb.answer()
    await _enter_chat(cb.from_user.id, cb.message, state, backend, ticket_id)


@router.message(SupportFlow.chatting, F.text.in_(kb.MENU_LABELS))
async def leave_chat_for_menu(message: Message, state: FSMContext, backend: AdminBackend) -> None:
    await state.clear()
    me = await _me(message, backend)
    await message.answer("از گفتگو خارج شدید.", reply_markup=kb.menu_for(me["role"] if me else "support"))


@router.message(SupportFlow.chatting, F.text == "خروج از گفتگو")
async def leave_chat(message: Message, state: FSMContext, backend: AdminBackend) -> None:
    await state.clear()
    me = await _me(message, backend)
    await message.answer("از گفتگو خارج شدید؛ گفتگو همچنان به شما واگذار است.",
                         reply_markup=kb.menu_for(me["role"] if me else "support"))


@router.message(SupportFlow.chatting, F.text == "پایان گفتگو")
async def end_chat(message: Message, state: FSMContext, backend: AdminBackend) -> None:
    data = await state.get_data()
    try:
        await backend.close_ticket(message.from_user.id, data["ticket_id"])
    except AdminBackendError as exc:
        await message.answer(exc.message)
        return
    await state.clear()
    me = await _me(message, backend)
    await message.answer("گفتگو بسته شد ✅", reply_markup=kb.menu_for(me["role"] if me else "support"))


@router.message(SupportFlow.chatting, F.text)
async def staff_reply(message: Message, state: FSMContext, backend: AdminBackend) -> None:
    data = await state.get_data()
    try:
        await backend.reply_ticket(message.from_user.id, data["ticket_id"], message.text)
    except AdminBackendError as exc:
        await message.answer(exc.message)
        return
    await message.answer("ارسال شد ✔️")


@router.message(F.text == "گزارش پشتیبانی")
async def support_report(message: Message, backend: AdminBackend) -> None:
    me = await _need_manager(message, backend)
    if not me:
        return
    rows = await backend.support_report(message.from_user.id)
    if not rows:
        await message.answer("هنوز گفتگویی پذیرفته نشده است.")
        return
    lines = ["📊 گزارش پشتیبانی"]
    for r in rows:
        avg = f"{fa(r['avg_minutes_to_close'])} دقیقه" if r["avg_minutes_to_close"] is not None else "—"
        lines.append(f"• {r['name']}: پذیرفته {fa(r['claimed'])} · بسته‌شده {fa(r['closed'])} · میانگین بستن {avg}")
    await message.answer("\n".join(lines))


# ---------- reports ----------

@router.message(F.text == "گزارش امروز")
async def today_report(message: Message, backend: AdminBackend) -> None:
    me = await _need_manager(message, backend)
    if not me:
        return
    try:
        report = await backend.daily_report(message.from_user.id)
    except AdminBackendError as exc:
        await message.answer(exc.message)
        return
    await message.answer(format_daily(report))


@router.message(F.text == "اکسل ماه جاری")
async def monthly_excel(message: Message, backend: AdminBackend) -> None:
    me = await _need_manager(message, backend)
    if not me:
        return
    now = datetime.now(ZoneInfo(os.environ.get("TIMEZONE", "Asia/Tehran")))
    ym = f"{now.year}-{now.month:02d}"
    try:
        data = await backend.monthly_excel(message.from_user.id, ym)
    except AdminBackendError as exc:
        await message.answer(exc.message)
        return
    await message.answer_document(BufferedInputFile(data, filename=f"NIV-monthly-{ym}.xlsx"),
                                  caption=f"گزارش ماهانه {ym}")


@router.message()
async def fallback(message: Message) -> None:
    await message.answer("از منوی زیر استفاده کنید.")
