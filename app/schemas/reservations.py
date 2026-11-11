from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.pricing import DesignCode, SpaceCode


def _must_be_aware(v: datetime) -> datetime:
    if v.tzinfo is None or v.utcoffset() is None:
        raise ValueError("booking_start must include a timezone offset")
    return v


class QuoteRequest(BaseModel):
    space_code: SpaceCode
    party_size: int = Field(ge=1, le=50)
    booking_start: datetime
    design: DesignCode = DesignCode.NONE
    with_cake: bool = False

    @field_validator("booking_start")
    @classmethod
    def _require_timezone(cls, v: datetime) -> datetime:
        return _must_be_aware(v)


class QuoteOut(BaseModel):
    total: int
    space_amount: int
    design_amount: int
    catering_amount: int
    items: list[dict]


class CreateReservationRequest(QuoteRequest):
    customer_name: str = Field(min_length=2, max_length=200)
    phone: str = Field(min_length=10, max_length=20)
    notes: str | None = Field(default=None, max_length=1000)
    telegram_user_id: int | None = None


class ReservationOut(BaseModel):
    public_code: str
    status: str
    total_amount: int
    price_snapshot: dict


class ConfirmRequest(BaseModel):
    table_ids: list[int] = Field(min_length=1, max_length=10)
    actor_telegram_id: int


class ReceiptRequest(BaseModel):
    storage_key: str = Field(min_length=1, max_length=500)
    telegram_user_id: int | None = None


class VerifyPaymentRequest(BaseModel):
    amount_verified: int = Field(ge=1)
    actor_telegram_id: int


class RejectRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    actor_telegram_id: int


class CancelRequest(BaseModel):
    telegram_user_id: int | None = None


class CancelOut(BaseModel):
    refund_amount: int
