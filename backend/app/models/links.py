from pydantic import BaseModel


class InternalLink(BaseModel):
    anchor_text: str
    target_topic: str


class ExternalRef(BaseModel):
    url: str
    title: str
    placement_context: str
