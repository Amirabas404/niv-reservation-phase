from pydantic import BaseModel, Field


class SupportOpenIn(BaseModel):
    telegram_user_id: int
    reason: str = Field(default="درخواست پشتیبانی", max_length=500)


class SupportCustomerMessageIn(BaseModel):
    telegram_user_id: int
    text: str = Field(min_length=1, max_length=2000)


class SupportCustomerIdIn(BaseModel):
    telegram_user_id: int


class SupportReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
