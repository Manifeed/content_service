from datetime import datetime

from pydantic import BaseModel, Field


class RssSourceAuthorRead(BaseModel):
    id: int
    name: str


class SourceListReadBase(BaseModel):
    id: int
    title: str
    authors: list[RssSourceAuthorRead] = Field(default_factory=list)
    url: str | None = None
    published_at: datetime | None = None
    company_names: list[str] = Field(default_factory=list)


class RssSourceRead(SourceListReadBase):
    image_url: str | None = None


class UserSourceRead(SourceListReadBase):
    pass


class RssSourcePageRead(BaseModel):
    items: list[RssSourceRead] = Field(default_factory=list)
    total: int = Field(ge=0, default=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class UserSourcePageRead(BaseModel):
    items: list[UserSourceRead] = Field(default_factory=list)
    total: int = Field(ge=0, default=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class SourceDetailBase(SourceListReadBase):
    summary: str | None = None
    feed_sections: list[str] = Field(default_factory=list)


class RssSourceDetailRead(SourceDetailBase):
    image_url: str | None = None


class UserSourceDetailRead(SourceDetailBase):
    pass
