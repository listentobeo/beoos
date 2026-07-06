from pydantic import BaseModel, Field


class PushKeys(BaseModel):
    p256dh: str = Field(min_length=10)
    auth: str = Field(min_length=10)


class PushSubscriptionCreate(BaseModel):
    endpoint: str = Field(min_length=20, max_length=2000)
    keys: PushKeys
    user_agent: str | None = Field(default=None, max_length=1000)


class PushSubscriptionStatus(BaseModel):
    enabled: bool
    vapid_public_key: str
