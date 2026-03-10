from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query

from app.db.neo4j_client import Neo4jClient
from app.models import CollaboratorRecommendation, Hotspot, SearchResult
from ingest_data import ingest_dummy_data
from recommendation_engine import RecommendationEngine
from schema import get_schema_statements
from search_engine import SearchEngine

app = FastAPI(title="Institutional Knowledge Intelligence Engine", version="1.0.0")


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
def ingest_dummy() -> dict:
    return ingest_dummy_data()


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