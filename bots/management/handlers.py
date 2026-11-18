import logging
import os
import re
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
SETTING_KEYS = ["pricing", "rules", "bank_card"]


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
    
