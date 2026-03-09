from pydantic import BaseModel


class FAQItem(BaseModel):
    question: str
    answer: str
