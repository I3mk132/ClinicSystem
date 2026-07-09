from pydantic import BaseModel, Field


class MessageResponse(BaseModel):
    detail: str


class VerifyConfirmRequest(BaseModel):
    code: str = Field(min_length=4, max_length=10)


class ForgotPasswordRequest(BaseModel):
    """`identifier` may be an email address or a phone number - whichever the person signed up with."""

    identifier: str = Field(min_length=3, max_length=150)


class ResetPasswordRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=150)
    code: str = Field(min_length=4, max_length=10)
    new_password: str = Field(min_length=8, max_length=128)
