from __future__ import annotations

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    id: str
    name: str | None = None
    score: float
    source: str = Field(description="vector|graph|hybrid")
    projects: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class CollaboratorRecommendation(BaseModel):
    candidate_id: str
    candidate_name: str
    score: float
    shared_skills: list[str]
    shared_interests: list[str]


class Hotspot(BaseModel):
    tag: str
    publication_count: int
    project_count: int
    momentum_score: float