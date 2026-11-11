from pydantic import BaseModel, Field


class AdminMe(BaseModel):
    telegram_user_id: int
    role: str
    display_name: str
    permissions: list[str]


class ConfirmByAdmin(BaseModel):
    table_ids: list[int] = Field(min_length=1, max_length=10)


class RejectByAdmin(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class PaymentVerifyByAdmin(BaseModel):
    amount_verified: int = Field(ge=1)


class TableUpdate(BaseModel):
    capacity: int | None = Field(default=None, ge=1, le=30)
    is_blocked: bool | None = None


class SettingUpdate(BaseModel):
    value: dict | int | str
    expected_version: int = Field(ge=1)
