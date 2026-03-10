from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable, SessionExpired
from openai import OpenAI
from sentence_transformers import SentenceTransformer

from app.config import settings
from app.db.neo4j_client import Neo4jClient


load_dotenv()


DEFAULT_VECTOR_DIMENSIONS = 1536
DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
PERSON_VECTOR_INDEX = "person_embeddings"


class SearchEngineError(RuntimeError):
    pass


def _env(name: str, fallback: str | None = None) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    if fallback:
        return os.getenv(fallback)
    return None


def get_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Query text must not be empty")

    api_key = _env("OPENAI_API_KEY") or settings.openai_api_key
    if not api_key:
        raise SearchEngineError("OPENAI_API_KEY is missing")

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(
        model=DEFAULT_EMBEDDING_MODEL,
        input=text.strip(),
    )
    vector = response.data[0].embedding
    if len(vector) != DEFAULT_VECTOR_DIMENSIONS:
        raise SearchEngineError(
            f"Unexpected embedding dimension: {len(vector)} (expected {DEFAULT_VECTOR_DIMENSIONS})"
        )
    return vector


def ensure_person_vector_index() -> None:
    uri = _env("NEO4J_URI") or settings.neo4j_uri
    user = _env("NEO4J_USERNAME", "NEO4J_USER") or settings.neo4j_user
    password = _env("NEO4J_PASSWORD") or settings.neo4j_password
    database = _env("NEO4J_DATABASE") or settings.neo4j_database

    if not uri or not user or not password:
        raise SearchEngineError("Neo4j credentials are missing in environment")

    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=10)
    try:
        with driver.session(database=database) as session:
            session.run(
                """
                CREATE VECTOR INDEX person_embeddings IF NOT EXISTS
                FOR (p:Person)
                ON (p.embedding)
                OPTIONS {indexConfig: {`vector.dimensions`: 1536, `vector.similarity_function`: 'cosine'}}
                """
            )
    except (ServiceUnavailable, SessionExpired, Neo4jError) as exc:
        raise SearchEngineError(f"Failed to ensure vector index: {exc}") from exc
    finally:
        driver.close()


def search_people(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    ensure_person_vector_index()
    used_fallback = False
    try:
        query_vector = get_embedding(query)
    except Exception:
        fallback_embedder = EmbeddingProvider()
        query_vector = fallback_embedder.embed_text(query)
        used_fallback = True

    uri = _env("NEO4J_URI") or settings.neo4j_uri
    user = _env("NEO4J_USERNAME", "NEO4J_USER") or settings.neo4j_user
    password = _env("NEO4J_PASSWORD") or settings.neo4j_password
    database = _env("NEO4J_DATABASE") or settings.neo4j_database

    driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=10)
    try:
        with driver.session(database=database) as session:
            vector_rows = session.run(
                """
                CALL db.index.vector.queryNodes($index_name, $top_k, $embedding)
                YIELD node, score
                WHERE node:Person
                OPTIONAL MATCH (node)-[:HAS_SKILL]->(s:Skill)
                WITH node, score, collect(DISTINCT s.name) AS all_skills
                WITH node,
                     score,
                     all_skills,
                     [sk IN all_skills WHERE toLower(sk) CONTAINS toLower($query)] AS related_skills,
                     toLower($query) AS q,
                     [sk IN all_skills WHERE sk IS NOT NULL][0..5] AS top_skills
                WITH node, score, related_skills, top_skills
                RETURN coalesce(node.id, elementId(node)) AS person_id,
                       node.name AS name,
                       node.department AS department,
                       score,
                       CASE WHEN size(related_skills) > 0 THEN related_skills[0..5] ELSE top_skills END AS skills
                ORDER BY score DESC
                LIMIT $top_k
                """,
                {
                    "index_name": PERSON_VECTOR_INDEX,
                    "top_k": top_k,
                    "embedding": query_vector,
                    "query": query,
                },
            )

            vector_results = [
                {
                    "person_id": row["person_id"],
                    "name": row["name"],
                    "department": row["department"],
                    "score": float(row["score"]),
                    "skills": row["skills"] or [],
                    "match_reason": (
                        f"Semantic similarity + skills: {', '.join((row['skills'] or [])[:3])}"
                        if row["skills"]
                        else "Semantic vector similarity"
                    )
                    + (" (local embedding fallback)" if used_fallback else ""),
                }
                for row in vector_rows
            ]

            if vector_results:
                return vector_results

            keyword_rows = session.run(
                """
                MATCH (p:Person)
                OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
                WITH p,
                     collect(DISTINCT s.name) AS skills,
                     toLower($query) AS q,
                     split(toLower($query), ' ') AS parts
                WITH p, skills, q, parts,
                     CASE WHEN toLower(coalesce(p.name, '')) CONTAINS q THEN 0.7 ELSE 0.0 END +
                     CASE WHEN toLower(coalesce(p.department, '')) CONTAINS q THEN 0.5 ELSE 0.0 END +
                     size([sk IN skills WHERE sk IS NOT NULL AND any(part IN parts WHERE part <> '' AND toLower(sk) CONTAINS part)]) * 0.25 AS relevance
                WHERE relevance > 0
                RETURN coalesce(p.id, elementId(p)) AS person_id,
                       p.name AS name,
                       p.department AS department,
                       relevance AS score,
                       [sk IN skills WHERE sk IS NOT NULL][0..5] AS skills
                ORDER BY relevance DESC, name ASC
                LIMIT $top_k
                """,
                {"query": query, "top_k": top_k},
            )

            return [
                {
                    "person_id": row["person_id"],
                    "name": row["name"],
                    "department": row["department"],
                    "score": float(row["score"]),
                    "skills": row["skills"] or [],
                    "match_reason": "Keyword fallback on Person profile fields",
                }
                for row in keyword_rows
            ]
    except (ServiceUnavailable, SessionExpired) as exc:
        raise SearchEngineError(
            "Neo4j connection failed or timed out during search. "
            "Verify URI/credentials/network and retry."
        ) from exc
    except Neo4jError as exc:
        raise SearchEngineError(f"Neo4j query failed: {exc}") from exc
    finally:
        driver.close()


def search_faculty_detailed(query: str, limit: int = 5) -> list[dict[str, Any]]:
    db = Neo4jClient()
    try:
        rows = db.run(
            """
            MATCH (f:Faculty)
            OPTIONAL MATCH (f)-[:HAS_SKILL]->(s:Skill)
            OPTIONAL MATCH (f)-[:WORKS_ON]->(p:ResearchProject)
            OPTIONAL MATCH (f)-[:AUTHORED]->(pub:Publication)
            WITH f,
                 collect(DISTINCT s.name) AS skills,
                 collect(DISTINCT p) AS projects,
                 collect(DISTINCT pub.title) AS publications
            WITH f,
                 skills,
                 [proj IN projects WHERE proj IS NOT NULL AND coalesce(proj.status, '') <> 'Completed' | proj.title] AS current_projects,
                 [proj IN projects WHERE proj IS NOT NULL AND coalesce(proj.status, '') = 'Completed' | proj.title] AS previous_projects,
                  publications
              WITH f,
                  skills,
                  current_projects,
                  previous_projects,
                                 [skill IN skills WHERE toLower(skill) CONTAINS toLower($query)] AS related_skills,
                                 [pr IN current_projects WHERE toLower(toString(pr)) CONTAINS toLower($query)] AS related_current_projects,
                                 [pr IN previous_projects WHERE toLower(toString(pr)) CONTAINS toLower($query)] AS related_previous_projects,
                                 [paper IN publications WHERE toLower(toString(paper)) CONTAINS toLower($query)] AS related_publications,
                 CASE
                     WHEN toLower(f.name) CONTAINS toLower($query)
                       OR toLower(coalesce(f.department, '')) CONTAINS toLower($query)
                       OR toLower(coalesce(f.email, '')) CONTAINS toLower($query)
                                             OR size([skill IN skills WHERE toLower(skill) CONTAINS toLower($query)]) > 0
                                             OR size([pr IN current_projects + previous_projects WHERE toLower(toString(pr)) CONTAINS toLower($query)]) > 0
                     THEN 1 ELSE 0
                                 END AS matched
            WHERE matched = 1
            RETURN f.id AS faculty_id,
                   f.name AS name,
                   f.department AS department,
                   f.email AS email,
                                     CASE WHEN size(related_skills) > 0 THEN related_skills[0..8] ELSE skills[0..8] END AS skills,
                                     CASE WHEN size(related_current_projects) > 0 THEN related_current_projects[0..8] ELSE current_projects[0..8] END AS current_projects,
                                     CASE WHEN size(related_previous_projects) > 0 THEN related_previous_projects[0..8] ELSE previous_projects[0..8] END AS previous_projects,
                                     CASE WHEN size(related_publications) > 0 THEN related_publications[0..8] ELSE [] END AS previous_publications
                        ORDER BY size(related_current_projects) DESC, size(related_previous_projects) DESC, name ASC
            LIMIT $limit
            """,
            {"query": query, "limit": limit},
        )
        return [
            {
                "faculty_id": row["faculty_id"],
                "name": row["name"],
                "department": row.get("department"),
                "email": row.get("email"),
                "skills": row.get("skills", []),
                "current_projects": row.get("current_projects", []),
                "previous_projects": row.get("previous_projects", []),
                "previous_publications": row.get("previous_publications", []),
            }
            for row in rows
        ]
    finally:
        db.close()


def search_projects_detailed(query: str, limit: int = 5) -> list[dict[str, Any]]:
    db = Neo4jClient()
    try:
        strict_rows = db.run(
            """
            MATCH (p:ResearchProject)
            WHERE toLower(p.title) CONTAINS toLower($query)
            OPTIONAL MATCH (f:Faculty)-[:WORKS_ON]->(p)
            OPTIONAL MATCH (s:Student)-[:WORKS_ON]->(p)
            OPTIONAL MATCH (author)-[:WORKS_ON]->(p)
            OPTIONAL MATCH (author)-[:AUTHORED]->(pub:Publication)
            WITH p,
                 collect(DISTINCT f.name) AS faculty_names,
                 collect(DISTINCT s.name) AS student_names,
                 collect(DISTINCT CASE
                   WHEN pub IS NOT NULL AND any(tag IN coalesce(pub.tags, []) WHERE tag IN coalesce(p.tags, []))
                   THEN pub.title
                 END) AS papers,
                 toLower($query) AS q
            RETURN p.id AS project_id,
                   p.title AS project_name,
                   p.description AS description,
                   p.status AS status,
                   p.progress AS progress,
                   coalesce(p.tags, []) AS tags,
                   faculty_names,
                   student_names,
                   CASE
                     WHEN coalesce(p.status, '') = 'Completed'
                     THEN [paper IN papers WHERE paper IS NOT NULL AND toLower(paper) CONTAINS q][0..8]
                     ELSE []
                   END AS related_papers,
                   100 AS relevance
            ORDER BY coalesce(p.progress, 0) DESC, project_name ASC
            LIMIT $limit
            """,
            {"query": query, "limit": limit},
        )

        rows = strict_rows if strict_rows else db.run(
            """
            MATCH (p:ResearchProject)
            WITH p,
                 toLower($query) AS q,
                 CASE WHEN toLower(p.title) CONTAINS toLower($query) THEN 3 ELSE 0 END +
                 CASE WHEN toLower(coalesce(p.description, '')) CONTAINS toLower($query) THEN 2 ELSE 0 END +
                 size([tag IN coalesce(p.tags, []) WHERE toLower(tag) CONTAINS toLower($query)]) AS relevance
            WHERE relevance > 0
            OPTIONAL MATCH (f:Faculty)-[:WORKS_ON]->(p)
            OPTIONAL MATCH (s:Student)-[:WORKS_ON]->(p)
            OPTIONAL MATCH (author)-[:WORKS_ON]->(p)
            OPTIONAL MATCH (author)-[:AUTHORED]->(pub:Publication)
            WITH p,
                 relevance,
                 q,
                 collect(DISTINCT f.name) AS faculty_names,
                 collect(DISTINCT s.name) AS student_names,
                 collect(DISTINCT CASE
                   WHEN pub IS NOT NULL AND any(tag IN coalesce(pub.tags, []) WHERE tag IN coalesce(p.tags, []))
                   THEN pub.title
                 END) AS papers
            RETURN p.id AS project_id,
                   p.title AS project_name,
                   p.description AS description,
                   p.status AS status,
                   p.progress AS progress,
                   coalesce(p.tags, []) AS tags,
                   faculty_names,
                   student_names,
                   CASE
                     WHEN coalesce(p.status, '') = 'Completed'
                     THEN [paper IN papers WHERE paper IS NOT NULL AND toLower(paper) CONTAINS q][0..8]
                     ELSE []
                   END AS related_papers
            ORDER BY relevance DESC, coalesce(p.progress, 0) DESC, project_name ASC
            LIMIT $limit
            """,
            {"query": query, "limit": limit},
        )

        return [
            {
                "project_id": row["project_id"],
                "project_name": row["project_name"],
                "description": row.get("description"),
                "status": row.get("status"),
                "progress": row.get("progress"),
                "tags": row.get("tags", []),
                "faculty_names": row.get("faculty_names", []),
                "student_names": row.get("student_names", []),
                "related_papers": row.get("related_papers", []),
            }
            for row in rows
        ]
    finally:
        db.close()


def sync_person_projections(include_embeddings: bool = True) -> dict[str, Any]:
    db = Neo4jClient()
    try:
        db.run(
            """
            MATCH (n)
            WHERE n:Faculty OR n:Student
            MERGE (p:Person {id: n.id})
            SET p.name = n.name,
                p.department = n.department,
                p.email = n.email,
                p.role = CASE WHEN n:Faculty THEN 'Faculty' ELSE 'Student' END
            """
        )

        db.run(
            """
            MATCH (n)-[:HAS_SKILL]->(s:Skill)
            WHERE n:Faculty OR n:Student
            MERGE (p:Person {id: n.id})
            MERGE (p)-[:HAS_SKILL]->(s)
            """
        )

        db.run(
            """
            MATCH (n)-[:WORKS_ON]->(r:ResearchProject)
            WHERE n:Faculty OR n:Student
            MERGE (p:Person {id: n.id})
            MERGE (p)-[:WORKS_ON]->(r)
            """
        )

        db.run(
            """
            MATCH (n)-[:AUTHORED]->(pub:Publication)
            WHERE n:Faculty OR n:Student
            MERGE (p:Person {id: n.id})
            MERGE (p)-[:AUTHORED]->(pub)
            """
        )

        ensure_person_vector_index()

        if include_embeddings:
            rows = db.run(
                """
                MATCH (p:Person)
                OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
                OPTIONAL MATCH (p)-[:WORKS_ON]->(r:ResearchProject)
                OPTIONAL MATCH (p)-[:AUTHORED]->(pub:Publication)
                WITH p,
                     collect(DISTINCT s.name) AS skills,
                     collect(DISTINCT r.title) AS projects,
                     collect(DISTINCT pub.title) AS publications
                RETURN p.id AS id,
                       p.name AS name,
                       p.department AS department,
                       skills,
                       projects,
                       publications
                """
            )

            embedder = EmbeddingProvider()
            texts = [
                (
                    f"Name: {row.get('name')}. "
                    f"Department: {row.get('department')}. "
                    f"Skills: {', '.join(row.get('skills') or [])}. "
                    f"Projects: {', '.join(row.get('projects') or [])}. "
                    f"Publications: {', '.join(row.get('publications') or [])}."
                )
                for row in rows
            ]

            vectors = embedder.embed_texts(texts)
            payload = [
                {"id": row["id"], "embedding": vectors[idx]}
                for idx, row in enumerate(rows)
            ]

            if payload:
                db.run(
                    """
                    UNWIND $rows AS row
                    MATCH (p:Person {id: row.id})
                    SET p.embedding = row.embedding
                    """,
                    {"rows": payload},
                )

        count_rows = db.run("MATCH (p:Person) RETURN count(p) AS total")
        total_people = int(count_rows[0]["total"]) if count_rows else 0
        return {
            "synced": total_people,
            "include_embeddings": include_embeddings,
        }
    finally:
        db.close()


class EmbeddingProvider:
    def __init__(self) -> None:
        self._st_model = None
        self._dimensions = DEFAULT_VECTOR_DIMENSIONS

    def embed_text(self, text: str) -> list[float]:
        if settings.openai_api_key:
            try:
                return self._coerce_dimensions(get_embedding(text))
            except Exception:
                pass
        if self._st_model is None:
            self._st_model = SentenceTransformer(settings.sentence_transformer_model)
        return self._coerce_dimensions(
            self._st_model.encode(text, normalize_embeddings=True).tolist()
        )

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        if settings.openai_api_key:
            try:
                api_key = _env("OPENAI_API_KEY") or settings.openai_api_key
                client = OpenAI(api_key=api_key)
                response = client.embeddings.create(
                    model=DEFAULT_EMBEDDING_MODEL,
                    input=texts,
                )
                vectors = [item.embedding for item in response.data]
                return [self._coerce_dimensions(v) for v in vectors]
            except Exception:
                pass

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
        try:
            people = search_people(query=query, top_k=min(limit, 10))
            if people:
                return [
                    {
                        "id": person["person_id"],
                        "name": person["name"],
                        "score": person["score"],
                        "source": "hybrid",
                        "skills": person["skills"],
                        "projects": [],
                    }
                    for person in people
                ]
        except Exception:
            pass

        query_embedding = self.embedder.embed_text(query)

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

        query_l = query.lower()
        for item in merged.values():
            skills = item.get("skills", []) or []
            projects = item.get("projects", []) or []
            related_skills = [skill for skill in skills if query_l in skill.lower()]
            related_projects = [project for project in projects if query_l in project.lower()]
            item["skills"] = related_skills[:5]
            item["projects"] = related_projects[:5]

        strictly_related = [
            item
            for item in merged.values()
            if item["skills"]
            or item["projects"]
            or query_l in (item.get("name") or "").lower()
        ]

        ranked = sorted(strictly_related, key=lambda x: x["score"], reverse=True)
        return ranked[:limit]


if __name__ == "__main__":
    sample_query = "Who works on sustainable polymers?"
    try:
        results = search_people(sample_query, top_k=3)
        print(f"Query: {sample_query}")
        for idx, row in enumerate(results, start=1):
            print(
                f"{idx}. {row['name']} ({row.get('department')}) | "
                f"score={row['score']:.4f} | skills={row.get('skills', [])}"
            )
    except Exception as exc:
        print(f"Search failed: {exc}")