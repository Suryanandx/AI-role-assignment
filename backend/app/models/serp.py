from pydantic import BaseModel


class SERPResult(BaseModel):
    rank: int
    url: str
    title: str
    snippet: str


class SERPAnalysis(BaseModel):
    themes: list[str] = []
    subtopics: list[str] = []
    paa_questions: list[str] = []
    keyword_candidates: list[str] = []
