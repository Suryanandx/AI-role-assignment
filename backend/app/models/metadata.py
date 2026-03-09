from pydantic import BaseModel


class SEOMetadata(BaseModel):
    title_tag: str
    meta_description: str
    primary_keyword: str
    secondary_keywords: list[str] = []
