from pydantic import BaseModel, EmailStr, Field


class WebsiteLeadSubmission(BaseModel):
    form_key: str | None = Field(default=None, max_length=200)
    name: str | None = Field(default=None, max_length=200)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=40)
    service: str | None = Field(default=None, max_length=120)
    budget: str | None = Field(default=None, max_length=120)
    deadline: str | None = Field(default=None, max_length=120)
    message: str = Field(min_length=2, max_length=8000)
    source_url: str | None = Field(default=None, max_length=2000)


class WebsiteLeadResult(BaseModel):
    status: str
    thread_id: str
    message: str
