from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.db.neo4j_client import Neo4jClient
from app.models import (
    CollaboratorRecommendation,
    FacultyDetailResult,
    GraphOverviewResponse,
    Hotspot,
    PersonSearchResult,
    ProjectDetailResult,
    SearchResult,
)
from ingest_data import ingest_dummy_data
from recommendation_engine import RecommendationEngine
from schema import get_schema_statements
from search_engine import (
    SearchEngine,
    search_faculty_detailed,
    search_people,
    search_projects_detailed,
    sync_person_projections,
)

app = FastAPI(title="Institutional Knowledge Intelligence Engine", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/admin/init-schema")
def init_schema() -> dict[str, str]:
    db = Neo4jClient()
    try:
        db.run_many(get_schema_statements())
    finally:
        db.close()
    return {"message": "Neo4j schema initialized"}


@app.post("/admin/ingest-dummy")
def ingest_dummy(
    include_embeddings: bool = Query(
        False,
        description="Set true to generate embeddings during ingestion (slower).",
    ),
    auto_sync_people: bool = Query(
        True,
        description="When true, auto-sync Faculty/Student into Person after ingestion.",
    ),
    sync_people_embeddings: bool = Query(
        True,
        description="When auto-sync is enabled, generate Person embeddings for semantic search.",
    ),
) -> dict:
    ingest_summary = ingest_dummy_data(include_embeddings=include_embeddings)
    if not auto_sync_people:
        return {"ingest": ingest_summary, "person_sync": None}

    sync_summary = sync_person_projections(include_embeddings=sync_people_embeddings)
    return {"ingest": ingest_summary, "person_sync": sync_summary}


@app.post("/admin/sync-people")
def sync_people(
    include_embeddings: bool = Query(
        True,
        description="Set true to populate Person.embedding vectors during sync.",
    ),
) -> dict:
    return sync_person_projections(include_embeddings=include_embeddings)


@app.get("/search/researchers", response_model=list[SearchResult])
def search_researchers(
    query: str = Query(..., min_length=3, description="Natural language query"),
    limit: int = Query(10, ge=1, le=50),
) -> list[SearchResult]:
    engine = SearchEngine()
    try:
        rows = engine.search_researchers(query=query, limit=limit)
        return [SearchResult(**r) for r in rows]
    finally:
        engine.db.close()


@app.get("/search/people", response_model=list[PersonSearchResult])
def semantic_search_people(
    query: str = Query(..., min_length=3, description="Natural language query for Person nodes"),
    top_k: int = Query(3, ge=1, le=20),
) -> list[PersonSearchResult]:
    try:
        rows = search_people(query=query, top_k=top_k)
        return [PersonSearchResult(**row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Semantic search unavailable: {exc}") from exc


@app.get("/search/faculty", response_model=list[FacultyDetailResult])
def semantic_search_faculty(
    query: str = Query(..., min_length=2, description="Faculty name, department, skill, or work query"),
    limit: int = Query(5, ge=1, le=20),
) -> list[FacultyDetailResult]:
    rows = search_faculty_detailed(query=query, limit=limit)
    return [FacultyDetailResult(**row) for row in rows]


@app.get("/search/projects", response_model=list[ProjectDetailResult])
def semantic_search_projects(
    query: str = Query(..., min_length=2, description="Project title, tag, or problem statement"),
    limit: int = Query(5, ge=1, le=20),
) -> list[ProjectDetailResult]:
    rows = search_projects_detailed(query=query, limit=limit)
    return [ProjectDetailResult(**row) for row in rows]


@app.get("/recommend/{user_id}", response_model=list[CollaboratorRecommendation])
def recommend_collaborators(user_id: str) -> list[CollaboratorRecommendation]:
    engine = RecommendationEngine()
    try:
        rows = engine.recommend_collaborators(user_id=user_id, limit=3)
        if not rows:
            raise HTTPException(status_code=404, detail="User not found or no collaborators available")
        return [CollaboratorRecommendation(**r) for r in rows]
    finally:
        engine.db.close()


@app.get("/analytics/hotspots", response_model=list[Hotspot])
def innovation_hotspots(years: int = Query(2, ge=1, le=10)) -> list[Hotspot]:
    engine = RecommendationEngine()
    try:
        rows = engine.innovation_hotspots(years=years)
        return [Hotspot(**r) for r in rows]
    finally:
        engine.db.close()


@app.get("/graph/overview", response_model=GraphOverviewResponse)
def graph_overview() -> GraphOverviewResponse:
    db = Neo4jClient()
    try:
        students = db.run("MATCH (n:Student) RETURN count(n) AS c")[0]["c"]
        faculty = db.run("MATCH (n:Faculty) RETURN count(n) AS c")[0]["c"]
        projects = db.run("MATCH (n:ResearchProject) RETURN count(n) AS c")[0]["c"]
        publications = db.run("MATCH (n:Publication) RETURN count(n) AS c")[0]["c"]
        skills = db.run("MATCH (n:Skill) RETURN count(n) AS c")[0]["c"]
        relationships = db.run(
            """
            MATCH ()-[r]->()
            WHERE type(r) IN ['WORKS_ON', 'HAS_SKILL', 'AUTHORED', 'AFFILIATED_WITH']
            RETURN count(r) AS c
            """
        )[0]["c"]

        connection_rows = db.run(
            """
            MATCH (s:Student)-[:WORKS_ON]->(p:ResearchProject)<-[:WORKS_ON]-(f:Faculty)
            OPTIONAL MATCH (s)-[:HAS_SKILL]->(sk:Skill)
            OPTIONAL MATCH (f)-[:AUTHORED]->(pub:Publication)
            WITH s, p, f,
                 collect(DISTINCT sk.name)[0..5] AS skills,
                 collect(DISTINCT pub.title)[0..5] AS publications
            RETURN s.name AS student_name,
                   p.title AS project_name,
                   f.name AS faculty_name,
                   skills,
                   publications
            ORDER BY project_name ASC
            LIMIT 8
            """
        )

        return GraphOverviewResponse(
            counts={
                "students": int(students),
                "faculty": int(faculty),
                "projects": int(projects),
                "publications": int(publications),
                "skills": int(skills),
                "relationships": int(relationships),
            },
            connections=connection_rows,
        )
    finally:
        db.close()