from pydantic import BaseModel, Field


class ArticleSection(BaseModel):
    level: int = Field(..., ge=1, le=3)
    heading: str
    content: str


class Article(BaseModel):
    sections: list[ArticleSection] = []
