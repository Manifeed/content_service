from pydantic import BaseModel, Field


class InternalServiceHealthRead(BaseModel):
    service: str = Field(min_length=1, max_length=80)
    status: str = Field(min_length=1, max_length=32)
