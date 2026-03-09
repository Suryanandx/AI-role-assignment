from pydantic import BaseModel, Field


class OutlineSection(BaseModel):
    heading_level: int = Field(..., ge=1, le=3)
    title: str
    bullet_points: list[str] = []


class Outline(BaseModel):
    sections: list[OutlineSection] = []
