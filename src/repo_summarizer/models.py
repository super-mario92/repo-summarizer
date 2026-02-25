from typing import Literal

from pydantic import BaseModel


class SummarizeRequest(BaseModel):
    github_url: str


class SummaryResponse(BaseModel):
    summary: str
    technologies: list[str]
    structure: str


class ErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    message: str
