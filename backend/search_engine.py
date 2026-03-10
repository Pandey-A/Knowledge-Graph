from __future__ import annotations

from typing import Any

from langchain_openai import OpenAIEmbeddings
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.db.neo4j_client import Neo4jClient


DEFAULT_VECTOR_DIMENSIONS = 1536


class EmbeddingProvider:
    def __init__(self) -> None:
        self._openai = None
        self._st_model = None
        self._dimensions = DEFAULT_VECTOR_DIMENSIONS

        if settings.openai_api_key:
            self._openai = OpenAIEmbeddings(
                model=settings.embedding_model,
                api_key=settings.openai_api_key,
            )
        else:
            self._st_model = SentenceTransformer(settings.sentence_transformer_model)

    def embed_text(self, text: str) -> list[float]:
        if self._openai is not None:
            return self._coerce_dimensions(self._openai.embed_query(text))
        if self._st_model is None:
            self._st_model = SentenceTransformer(settings.sentence_transformer_model)
        return self._coerce_dimensions(
            self._st_model.encode(text, normalize_embeddings=True).tolist()
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if self._openai is not None:
            vectors = self._openai.embed_documents(texts)
            return [self._coerce_dimensions(v) for v in vectors]

        if self._st_model is None:
            self._st_model = SentenceTransformer(settings.sentence_transformer_model)
        vectors = self._st_model.encode(texts, normalize_embeddings=True)
        return [self._coerce_dimensions(v.tolist()) for v in vectors]

    def _coerce_dimensions(self, vector: list[float]) -> list[float]:
        if len(vector) == self._dimensions:
            return vector
        if len(vector) > self._dimensions:
            return vector[: self._dimensions]
        return vector + [0.0] * (self._dimensions - len(vector))


class SearchEngine:
    def __init__(self, db: Neo4jClient | None = None) -> None:
        self.db = db or Neo4jClient()
        self.embedder = EmbeddingProvider()

    def search_researchers(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        query_embedding = self.embedder.embed_text(query)

        pinecone_hits = self._search_pinecone(query_embedding=query_embedding, limit=limit)

        vector_hits = self.db.run(
            """
            CALL db.index.vector.queryNodes('research_entity_embeddings', $limit, $embedding)
            YIELD node, score
            WITH node, score
            MATCH (r)-[:WORKS_ON|AUTHORED]->(node)
            WHERE r:Faculty OR r:Student
            OPTIONAL MATCH (r)-[:HAS_SKILL]->(s:Skill)
            OPTIONAL MATCH (r)-[:WORKS_ON]->(p:ResearchProject)
            RETURN r.id AS id,
                   r.name AS name,
                   max(score) AS vector_score,
                   collect(DISTINCT s.name)[0..5] AS skills,
                   collect(DISTINCT p.title)[0..5] AS projects
            ORDER BY vector_score DESC
            LIMIT $limit
            """,
            {"embedding": query_embedding, "limit": limit},
        )

        graph_hits = self.db.run(
            """
            MATCH (r)
            WHERE r:Faculty OR r:Student
            OPTIONAL MATCH (r)-[:WORKS_ON]->(p:ResearchProject)
            OPTIONAL MATCH (r)-[:HAS_SKILL]->(s:Skill)
            WITH r, collect(DISTINCT p.title) AS projects, collect(DISTINCT s.name) AS skills
            WITH r, projects, skills,
                 CASE WHEN any(x IN projects WHERE toLower(x) CONTAINS toLower($query)) THEN 1.0 ELSE 0.0 END +
                 CASE WHEN any(x IN skills WHERE toLower(x) CONTAINS toLower($query)) THEN 1.0 ELSE 0.0 END AS graph_score
            WHERE graph_score > 0
            RETURN r.id AS id, r.name AS name, graph_score, skills[0..5] AS skills, projects[0..5] AS projects
            ORDER BY graph_score DESC
            LIMIT $limit
            """,
            {"query": query, "limit": limit},
        )

        merged: dict[str, dict[str, Any]] = {}
        for row in pinecone_hits:
            merged[row["id"]] = {
                "id": row["id"],
                "name": row.get("name"),
                "score": float(row.get("score", 0.0)) * 0.55,
                "source": "vector",
                "skills": row.get("skills", []),
                "projects": row.get("projects", []),
            }

        for row in vector_hits:
            existing = merged.get(row["id"], {})
            merged[row["id"]] = {
                "id": row["id"],
                "name": row.get("name"),
                "score": float(existing.get("score", 0.0)) + float(row.get("vector_score", 0.0)) * 0.75,
                "source": "vector" if not existing else "hybrid",
                "skills": row.get("skills", []) or existing.get("skills", []),
                "projects": row.get("projects", []) or existing.get("projects", []),
            }

        for row in graph_hits:
            item = merged.setdefault(
                row["id"],
                {
                    "id": row["id"],
                    "name": row.get("name"),
                    "score": 0.0,
                    "source": "graph",
                    "skills": row.get("skills", []),
                    "projects": row.get("projects", []),
                },
            )
            item["score"] += float(row.get("graph_score", 0.0)) * 0.25
            item["source"] = "hybrid"

        ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:limit]

    def _search_pinecone(self, query_embedding: list[float], limit: int) -> list[dict[str, Any]]:
        if not settings.pinecone_api_key or not settings.pinecone_index:
            return []

        pc = Pinecone(api_key=settings.pinecone_api_key)
        index = pc.Index(settings.pinecone_index)
        response = index.query(
            vector=query_embedding,
            top_k=limit,
            include_metadata=True,
        )

        results: list[dict[str, Any]] = []
        for match in response.matches:
            md = match.metadata or {}
            results.append(
                {
                    "id": md.get("researcher_id", match.id),
                    "name": md.get("name"),
                    "score": match.score,
                    "skills": md.get("skills", []),
                    "projects": md.get("projects", []),
                }
            )
        return results