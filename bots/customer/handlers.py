import logging
from datetime import datetime
from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from bots.customer import keyboards as kb
from bots.customer.backend_client import BackendClient, BackendError
from bots.customer.formatting import (
    DESIGN_NAMES,
    SPACE_NAMES,
    STATUS_NAMES,
    TZ,
    fa,
    jalali_datetime_label,
    local_start_utc,
    money,
    time_slots,
    upcoming_dates,
)
from bots.customer.states import BookingStates, ReceiptStates, StatusStates, SupportStates

log = logging.getLogger(__name__)
router = Router(name="customer")

FLOW_RESET_TEXT = "درخواست قبلی لغو شد. به منوی اصلی برگشتید."
PLAIN_SUCCESS_TEXT = (
    "درخواست رزرو شما با موفقیت ثبت شد 🌷\n\n"
    "درخواست شما به مجموعه اعلام خواهد شد و پذیرایی بر اساس اولویت و هماهنگی مجموعه انجام می‌شود.\n\n"
    "از انتخاب شما سپاسگزاریم ❤️"
)
REJECTED_UNPAID_TEXT = (
    "مشتری گرامی 🌷\n\n"
    "به دلیل عدم پرداخت در زمان تعیین‌شده، درخواست رزرو شما رد شد.\n\n"
    "از همراهی شما سپاسگزاریم.\n\n"
    "کافه‌رستوران NIV ❤️"
)
SUPPORT_TEXT = (
    "درخواست شما به واحد پشتیبانی NIV ارجاع شد 🌷\n"
    "لطفاً منتظر بمانید؛ همکاران ما در اولین فرصت با شما ارتباط می‌گیرند."
)


# ---------- helpers ----------

async def _edit_or_answer(cb: CallbackQuery, text: str, markup=None) -> None:
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except Exception:  # noqa: BLE001 - message may be unchanged or too old to edit
        await cb.message.answer(text, reply_markup=markup)
    await cb.answer()


def _booking_summary(data: dict, quote: dict) -> str:
    start_local = local_start_utc(
        datetime.fromisoformat(data["date"]).date(), data["time"]
    )
    lines = [
        "📋 خلاصه رزرو",
        f"📅 تاریخ: {jalali_datetime_label(start_local)}",
        f"👥 تعداد نفرات: {fa(data['party_size'])}",
        f"🪑 فضا: {SPACE_NAMES[data['space']]}",
        f"🎨 دیزاین: {DESIGN_NAMES[data['design']]}",
        f"🎂 پذیرایی کیک: {'بله' if data['with_cake'] else 'خیر'}",
        f"👤 نام: {data['name']}",
        f"📱 موبایل: {fa(data['phone'])}",
        "",
        "💰 جزئیات مبلغ:",
    ]
    for item in quote["items"]:
        lines.append(f"• {item['label']}: {money(item['total'])}")
    lines.append("")
    lines.append(f"مبلغ کل: {money(quote['total'])}")
    return "\n".join(lines)


def _payment_text(code: str, amount: int, card: str | None, owner: str | None) -> str:
    return (
        f"کد پیگیری شما: {code}\n\n"
        "رزرو با دیزاین نیاز به پرداخت کامل دارد.\n"
        f"مبلغ قابل پرداخت: {money(amount)}\n"
        f"شماره کارت: {fa(card or '---')}\n"
        f"به نام: {owner or '---'}\n\n"
        "پس از واریز، تصویر رسید را همین‌جا ارسال کنید.\n"
        "توجه: ارسال رسید به معنی پرداخت موفق نیست و پس از بررسی مجموعه تأیید می‌شود."
    )


# ---------- global ----------

@router.message(CommandStart())
async def start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "سلام! به ربات رزرو کافه‌رستوران NIV خوش آمدید 🌷\nلطفاً یکی از گزینه‌های زیر را انتخاب کنید.",
        reply_markup=kb.main_menu(),
    )


@router.message(Command("cancel"))
@router.message(F.text == kb.BTN_CANCEL)
async def abort(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(FLOW_RESET_TEXT, reply_markup=kb.main_menu())


@router.message(F.text == kb.BTN_INFO)
async def info(message: Message, backend: BackendClient) -> None:
    try:
        v = await backend.venue()
    except BackendError as exc:
        await message.answer(exc.message)
        return
    await message.answer(
        f"📍 {v['name']}\n{v['address']}\n\n"
        f"📞 {fa(v['phone'])}\n\n"
        f"🕒 پذیرایی داخل مجموعه: {fa(v['dine_in_open'])} تا {fa(v['dine_in_close'])}\n"
        "پس از آن فقط بیرون‌بر انجام می‌شود."
    )


async def _start_support(message: Message, state: FSMContext, backend: BackendClient, user_id: int) -> None:
    try:
        await backend.open_support(user_id)
    except BackendError as exc:
        await message.answer(exc.message, reply_markup=kb.main_menu())
        return
    await state.clear()
    await state.set_state(SupportStates.chat)
    await message.answer(SUPPORT_TEXT, reply_markup=kb.support_chat_kb())


@router.message(F.text == kb.BTN_SUPPORT)
async def support_menu(message: Message, state: FSMContext, backend: BackendClient) -> None:
    await _start_support(message, state, backend, message.from_user.id)


@router.message(SupportStates.chat, F.text == kb.BTN_END_CHAT)
async def support_end(message: Message, state: FSMContext, backend: BackendClient) -> None:
    try:
        await backend.close_support(message.from_user.id)
    except BackendError:
        pass
    await state.clear()
    await message.answer("گفتگو پایان یافت. ممنون از همراهی شما 🌷", reply_markup=kb.main_menu())


@router.message(SupportStates.chat, F.text)
async def support_chat_text(message: Message, state: FSMContext, backend: BackendClient) -> None:
    try:
        await backend.support_message(message.from_user.id, message.text)
    except BackendError as exc:
        if exc.code == "no_active_ticket":
            await state.clear()
            await message.answer("این گفتگو پایان یافته است. برای پیام جدید دوباره از منو پشتیبانی را انتخاب کنید.",
                                 reply_markup=kb.main_menu())
            return
        await message.answer(exc.message)


@router.message(SupportStates.chat)
async def support_chat_other(message: Message) -> None:
    await message.answer("در گفتگو با پشتیبانی فقط پیام متنی ارسال کنید.", reply_markup=kb.support_chat_kb())


# ---------- booking flow ----------

@router.message(F.text == kb.BTN_BOOK)
async def book_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BookingStates.date)
    await message.answer("تاریخ موردنظر را انتخاب کنید:", reply_markup=kb.cancel_only())
    today = datetime.now(TZ).date()
    await message.answer("📅", reply_markup=kb.dates_kb(upcoming_dates(today)))


@router.callback_query(BookingStates.date, F.data.startswith("d:"))
async def pick_date(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(date=cb.data.split(":", 1)[1])
    await state.set_state(BookingStates.time)
    await _edit_or_answer(cb, "ساعت ورود را انتخاب کنید:", kb.times_kb(time_slots()))


@router.callback_query(BookingStates.time, F.data.startswith("t:"))
async def pick_time(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(time=cb.data.split(":", 1)[1])
    await state.set_state(BookingStates.party)
    await _edit_or_answer(cb, "تعداد نفرات را انتخاب کنید:", kb.party_kb())


@router.callback_query(BookingStates.party, F.data == "p:more")
async def party_too_large(cb: CallbackQuery) -> None:
    await _edit_or_answer(
        cb,
        "برای گروه‌های بیش از ۱۰ نفر، لطفاً با پشتیبانی هماهنگ کنید.",
        kb.support_offer_kb(),
    )


@router.callback_query(BookingStates.party, F.data.startswith("p:"))
async def pick_party(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(party_size=int(cb.data.split(":", 1)[1]))
    await state.set_state(BookingStates.space)
    await _edit_or_answer(cb, "فضای موردنظر را انتخاب کنید:", kb.spaces_kb())


@router.callback_query(BookingStates.space, F.data.startswith("s:"))
async def pick_space(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(space=cb.data.split(":", 1)[1])
    await state.set_state(BookingStates.design)
    await _edit_or_answer(cb, "نوع دیزاین را انتخاب کنید (اختیاری):", kb.designs_kb())


@router.callback_query(BookingStates.design, F.data.startswith("g:"))
async def pick_design(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(design=cb.data.split(":", 1)[1])
    await state.set_state(BookingStates.cake)
    await _edit_or_answer(cb, "آیا کیک از بیرون می‌آورید؟", kb.cake_kb())


@router.callback_query(BookingStates.cake, F.data.startswith("c:"))
async def pick_cake(cb: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(with_cake=cb.data.endswith("1"))
    await state.set_state(BookingStates.name)
    await _edit_or_answer(cb, "نام و نام خانوادگی خود را وارد کنید:")


@router.message(BookingStates.name, F.text)
async def enter_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2:
        await message.answer("لطفاً نام معتبر وارد کنید.")
        return
    await state.update_data(name=name)
    await state.set_state(BookingStates.phone)
    await message.answer(
        "برای ثبت رزرو، شماره موبایل خود را از طریق دکمه زیر ارسال کنید.",
        reply_markup=kb.contact_request(),
    )


@router.message(BookingStates.phone, F.contact)
async def enter_phone(message: Message, state: FSMContext, backend: BackendClient) -> None:
    if message.contact.user_id not in (None, message.from_user.id):
        await message.answer("لطفاً شماره خودتان را با دکمه ارسال شماره من بفرستید.")
        return
    data = await state.get_data()
    phone = message.contact.phone_number
    await state.update_data(phone=phone)
    payload = {
        "space_code": data["space"],
        "party_size": data["party_size"],
        "booking_start": local_start_utc(datetime.fromisoformat(data["date"]).date(), data["time"]).isoformat(),
        "design": data["design"],
        "with_cake": data["with_cake"],
    }
    try:
        quote = await backend.quote(payload)
    except BackendError as exc:
        await state.set_state(BookingStates.date)
        await message.answer(exc.message, reply_markup=kb.main_menu())
        if exc.support_offer:
            await message.answer("اگر مایل هستید، می‌توانید با پشتیبانی صحبت کنید.", reply_markup=kb.support_offer_kb())
        await state.clear()
        return

    await state.update_data(quote_total=quote["total"])
    await state.set_state(BookingStates.confirm)
    await message.answer("ممنون. ✅", reply_markup=ReplyKeyboardRemove())
    await message.answer(_booking_summary(await state.get_data(), quote), reply_markup=kb.confirm_kb())


@router.message(BookingStates.phone, F.text)
async def phone_not_shared(message: Message) -> None:
    await message.answer("لطفاً از دکمه «ارسال شماره من» استفاده کنید.", reply_markup=kb.contact_request())


@router.callback_query(BookingStates.confirm, F.data == "restart")
async def restart(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await cb.message.answer(FLOW_RESET_TEXT, reply_markup=kb.main_menu())
    await cb.answer()


@router.callback_query(BookingStates.confirm, F.data == "ok")
async def confirm(cb: CallbackQuery, state: FSMContext, backend: BackendClient) -> None:
    data = await state.get_data()
    payload = {
        "customer_name": data["name"],
        "phone": data["phone"],
        "space_code": data["space"],
        "party_size": data["party_size"],
        "booking_start": local_start_utc(datetime.fromisoformat(data["date"]).date(), data["time"]).isoformat(),
        "design": data["design"],
        "with_cake": data["with_cake"],
        "telegram_user_id": cb.from_user.id,
    }
    try:
        created = await backend.create_reservation(payload)
    except BackendError as exc:
        await state.clear()
        await _edit_or_answer(cb, exc.message)
        if exc.support_offer:
            await cb.message.answer("می‌توانید با پشتیبانی صحبت کنید.", reply_markup=kb.support_offer_kb())
        return

    await state.clear()
    code = created["public_code"]
    if payload["design"] != "none":
        try:
            venue = await backend.venue()
        except BackendError:
            venue = {}
        await state.set_state(ReceiptStates.waiting_photo)
        await state.update_data(receipt_code=code)
        await _edit_or_answer(cb, "درخواست شما ثبت شد. برای تکمیل رزرو، پرداخت را انجام دهید.")
        await cb.message.answer(
            _payment_text(code, created["total_amount"], venue.get("card_number"), venue.get("card_owner")),
            reply_markup=kb.cancel_only(),
        )
    else:
        await _edit_or_answer(cb, PLAIN_SUCCESS_TEXT)
        await cb.message.answer(f"کد پیگیری: {code}", reply_markup=kb.main_menu())


@router.callback_query(F.data == "support")
async def support_from_offer(cb: CallbackQuery, state: FSMContext, backend: BackendClient) -> None:
    await _start_support(cb.message, state, backend, cb.from_user.id)
    await cb.answer()


# ---------- status, cancellation, receipts ----------

@router.message(F.text == kb.BTN_STATUS)
async def status_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(StatusStates.phone)
    await message.answer(
        "برای نمایش رزروهای شما، شماره موبایل خود را از طریق دکمه زیر ارسال کنید.",
        reply_markup=kb.contact_request(),
    )


@router.message(StatusStates.phone, F.contact)
async def status_show(message: Message, state: FSMContext, backend: BackendClient) -> None:
    if message.contact.user_id not in (None, message.from_user.id):
        await message.answer("لطفاً شماره خودتان را ارسال کنید.")
        return
    await state.clear()
    try:
        items = await backend.list_reservations(message.contact.phone_number)
    except BackendError as exc:
        await message.answer(exc.message, reply_markup=kb.main_menu())
        return
    if not items:
        await message.answer("رزروی برای این شماره پیدا نشد.", reply_markup=kb.main_menu())
        return

    await message.answer("رزروهای شما:", reply_markup=kb.main_menu())
    for r in items:
        status = r["status"]
        text = (
            f"کد: {r['public_code']}\n"
            f"📅 {jalali_datetime_label(datetime.fromisoformat(r['booking_start']))}\n"
            f"👥 {fa(r['party_size'])} نفر · {SPACE_NAMES.get(r['space_name'], r['space_name'])}\n"
            f"وضعیت: {STATUS_NAMES.get(status, status)}"
        )
        can_receipt = status == "awaiting_payment"
        can_cancel = status in {"pending_manager_approval", "awaiting_payment", "receipt_submitted", "confirmed"}
        await message.answer(
            text,
            reply_markup=kb.reservation_actions_kb(r["public_code"], can_receipt, can_cancel)
            if (can_receipt or can_cancel) else None,
        )


@router.callback_query(F.data.startswith("cx:"))
async def cancel_request(cb: CallbackQuery, backend: BackendClient) -> None:
    code = cb.data.split(":", 1)[1]
    try:
        result = await backend.cancel(code, cb.from_user.id)
    except BackendError as exc:
        await _edit_or_answer(cb, exc.message)
        if exc.support_offer:
            await cb.message.answer("برای لغو، با پشتیبانی هماهنگ کنید.", reply_markup=kb.support_offer_kb())
        return
    refund = result.get("refund_amount", 0)
    text = f"رزرو {code} لغو شد."
    if refund:
        text += f"\nمبلغ بازگشتی (۵۰٪): {money(refund)} — پس از بررسی مجموعه واریز می‌شود."
    await _edit_or_answer(cb, text)


@router.callback_query(F.data.startswith("rc:"))
async def receipt_request(cb: CallbackQuery, state: FSMContext) -> None:
    code = cb.data.split(":", 1)[1]
    await state.set_state(ReceiptStates.waiting_photo)
    await state.update_data(receipt_code=code)
    await cb.message.answer("تصویر رسید پرداخت را ارسال کنید.", reply_markup=kb.cancel_only())
    await cb.answer()


@router.message(ReceiptStates.waiting_photo, F.photo)
async def receipt_received(message: Message, state: FSMContext, backend: BackendClient) -> None:
    data = await state.get_data()
    code = data.get("receipt_code")
    buffer = BytesIO()
    await message.bot.download(message.photo[-1], destination=buffer)
    try:
        await backend.upload_receipt(code, buffer.getvalue(), "image/jpeg", message.from_user.id)
    except BackendError as exc:
        await message.answer(exc.message)
        return
    await state.clear()
    await message.answer(
        "رسید شما دریافت شد 🌷\nپس از بررسی و تأیید پرداخت توسط مجموعه، رزرو نهایی می‌شود.",
        reply_markup=kb.main_menu(),
    )


@router.message(ReceiptStates.waiting_photo)
async def receipt_wrong_input(message: Message) -> None:
    await message.answer("لطفاً تصویر رسید را ارسال کنید، یا «انصراف» را بزنید.")


@router.message()
async def fallback(message: Message) -> None:
    await message.answer("متوجه نشدم. لطفاً از منوی زیر استفاده کنید.", reply_markup=kb.main_menu())
