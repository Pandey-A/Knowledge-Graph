from __future__ import annotations

from typing import Any

from app.db.neo4j_client import Neo4jClient


COLLABORATOR_QUERY = """
MATCH (u)
WHERE (u:Faculty OR u:Student) AND u.id = $user_id

MATCH (candidate)
WHERE (candidate:Faculty OR candidate:Student) AND candidate.id <> u.id

OPTIONAL MATCH (u)-[:HAS_SKILL]->(s:Skill)<-[:HAS_SKILL]-(candidate)
WITH u, candidate, collect(DISTINCT s.name) AS shared_skills

OPTIONAL MATCH (u)-[:WORKS_ON|AUTHORED]->(up)
OPTIONAL MATCH (candidate)-[:WORKS_ON|AUTHORED]->(cp)
WITH u, candidate, shared_skills,
     [x IN collect(DISTINCT up.tags) WHERE x IS NOT NULL] AS u_tag_lists,
     [x IN collect(DISTINCT cp.tags) WHERE x IS NOT NULL] AS c_tag_lists

WITH candidate, shared_skills,
     reduce(uTags = [], arr IN u_tag_lists | uTags + arr) AS u_tags,
     reduce(cTags = [], arr IN c_tag_lists | cTags + arr) AS c_tags

WITH candidate, shared_skills,
     [tag IN u_tags WHERE tag IN c_tags] AS shared_interests,
     size(shared_skills) AS common_neighbors_score,
     size([tag IN u_tags WHERE NOT tag IN c_tags]) + size([tag IN c_tags WHERE NOT tag IN u_tags]) AS complementarity

WITH candidate, shared_skills, shared_interests,
     (common_neighbors_score * 2.0) + size(shared_interests) + (0.3 * complementarity) AS score

RETURN candidate.id AS candidate_id,
       candidate.name AS candidate_name,
       score,
       shared_skills[0..5] AS shared_skills,
       shared_interests[0..5] AS shared_interests
ORDER BY score DESC
LIMIT $limit
"""


HOTSPOT_QUERY = """
WITH date() - duration({years: $years}) AS cutoff

MATCH (p:Publication)
WHERE p.published_at >= cutoff
UNWIND coalesce(p.tags, []) AS pub_tag
WITH pub_tag AS tag, count(*) AS publication_count, cutoff

OPTIONAL MATCH (r:ResearchProject)
WHERE r.created_at >= cutoff AND tag IN coalesce(r.tags, [])
WITH tag, publication_count, count(r) AS project_count

WITH tag, publication_count, project_count,
     (publication_count * 1.5 + project_count) AS momentum_score
WHERE publication_count > 0 OR project_count > 0

RETURN tag, publication_count, project_count, momentum_score
ORDER BY momentum_score DESC
LIMIT 10
"""


class RecommendationEngine:
    def __init__(self, db: Neo4jClient | None = None) -> None:
        self.db = db or Neo4jClient()

    def recommend_collaborators(self, user_id: str, limit: int = 3) -> list[dict[str, Any]]:
        return self.db.run(COLLABORATOR_QUERY, {"user_id": user_id, "limit": limit})

    def innovation_hotspots(self, years: int = 2) -> list[dict[str, Any]]:
        return self.db.run(HOTSPOT_QUERY, {"years": years})