from __future__ import annotations

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    id: str
    name: str | None = None
    score: float
    source: str = Field(description="vector|graph|hybrid")
    projects: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)


class PersonSearchResult(BaseModel):
    person_id: str
    name: str | None = None
    department: str | None = None
    score: float
    skills: list[str] = Field(default_factory=list)
    match_reason: str


class FacultyDetailResult(BaseModel):
    faculty_id: str
    name: str
    department: str | None = None
    email: str | None = None
    skills: list[str] = Field(default_factory=list)
    current_projects: list[str] = Field(default_factory=list)
    previous_projects: list[str] = Field(default_factory=list)
    previous_publications: list[str] = Field(default_factory=list)


class ProjectDetailResult(BaseModel):
    project_id: str
    project_name: str
    description: str | None = None
    status: str | None = None
    progress: int | None = None
    tags: list[str] = Field(default_factory=list)
    faculty_names: list[str] = Field(default_factory=list)
    student_names: list[str] = Field(default_factory=list)
    related_papers: list[str] = Field(default_factory=list)


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


class StudentSingleMatchResult(BaseModel):
    match_type: str
    match_id: str
    match_name: str
    department: str | None = None
    score: float
    reason: str
    overlap_topics: list[str] = Field(default_factory=list)
    required_course: str | None = None
    project_status: str | None = None
    project_progress: int | None = None


class GraphOverviewCounts(BaseModel):
    students: int
    faculty: int
    projects: int
    publications: int
    skills: int
    relationships: int


class GraphConnectionSample(BaseModel):
    student_name: str
    project_name: str
    faculty_name: str
    skills: list[str] = Field(default_factory=list)
    publications: list[str] = Field(default_factory=list)


class GraphOverviewResponse(BaseModel):
    counts: GraphOverviewCounts
    connections: list[GraphConnectionSample] = Field(default_factory=list)