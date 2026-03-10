from __future__ import annotations

import json
from pathlib import Path
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


STUDENT_SINGLE_MATCH_QUERY = """
WITH toLower(trim($topic)) AS topic_lc,
     toLower(trim($course)) AS course_lc,
     toFloat($cgpa) AS cgpa

CALL {
    WITH topic_lc, course_lc, cgpa
    MATCH (f:Faculty)
    OPTIONAL MATCH (f)-[:HAS_SKILL]->(s:Skill)
    OPTIONAL MATCH (f)-[:WORKS_ON]->(p:ResearchProject)
        WITH f, topic_lc, course_lc, cgpa,
         collect(DISTINCT toLower(coalesce(s.name, ''))) AS faculty_skill_lc,
         collect(DISTINCT toLower(coalesce(p.title, ''))) AS faculty_project_titles_lc,
         collect(DISTINCT toLower(coalesce(f.department, ''))) AS faculty_department_lc,
         collect(DISTINCT coalesce(s.name, '')) AS faculty_skill_names
        WITH f, topic_lc, course_lc, cgpa,
         faculty_skill_lc,
         faculty_project_titles_lc,
         faculty_department_lc,
         [name IN faculty_skill_names WHERE name <> '' AND topic_lc CONTAINS toLower(name)] AS overlap_topics,
         CASE
             WHEN topic_lc = '' THEN 0.0
             ELSE (
                 CASE WHEN any(x IN faculty_skill_lc WHERE x <> '' AND (x CONTAINS topic_lc OR topic_lc CONTAINS x)) THEN 55.0 ELSE 0.0 END +
                 CASE WHEN any(x IN faculty_project_titles_lc WHERE x <> '' AND (x CONTAINS topic_lc OR topic_lc CONTAINS x)) THEN 15.0 ELSE 0.0 END
             )
         END AS topic_score,
         CASE
             WHEN course_lc = '' THEN 0.0
             WHEN any(x IN faculty_department_lc WHERE x <> '' AND (x CONTAINS course_lc OR course_lc CONTAINS x)) THEN 20.0
             ELSE 0.0
         END AS course_score,
         CASE
             WHEN cgpa >= 9.0 THEN 25.0
             WHEN cgpa >= 8.0 THEN 20.0
             WHEN cgpa >= 7.0 THEN 14.0
             WHEN cgpa >= 6.0 THEN 8.0
             ELSE 3.0
         END AS cgpa_score
    WITH f, overlap_topics, topic_score + course_score + cgpa_score AS score
    RETURN {
        match_type: 'faculty',
        match_id: f.id,
        match_name: f.name,
        department: f.department,
        score: score,
        reason: 'Strong alignment with your topic, course, and profile.',
        overlap_topics: overlap_topics[0..5],
        required_course: null,
        project_status: null,
        project_progress: null
    } AS candidate

    UNION

    WITH topic_lc, course_lc, cgpa
    MATCH (p:ResearchProject)
    WITH p, topic_lc, course_lc, cgpa,
         toLower(coalesce(p.title, '')) AS title_lc,
         toLower(coalesce(p.description, '')) AS desc_lc,
         [tag IN coalesce(p.tags, []) | toLower(toString(tag))] AS tag_lc,
         coalesce(p.tags, []) AS tag_names,
         toLower(coalesce(p.department, '')) AS project_department_lc
    WITH p, topic_lc, course_lc, cgpa, title_lc, desc_lc, tag_lc, tag_names, project_department_lc,
         CASE
             WHEN topic_lc = '' THEN 0.0
             ELSE (
                 CASE WHEN title_lc <> '' AND (title_lc CONTAINS topic_lc OR topic_lc CONTAINS title_lc) THEN 45.0 ELSE 0.0 END +
                 CASE WHEN any(x IN tag_lc WHERE x <> '' AND (x CONTAINS topic_lc OR topic_lc CONTAINS x)) THEN 30.0 ELSE 0.0 END +
                 CASE WHEN desc_lc <> '' AND (desc_lc CONTAINS topic_lc OR topic_lc CONTAINS desc_lc) THEN 10.0 ELSE 0.0 END
             )
         END AS topic_score,
         CASE
             WHEN course_lc = '' THEN 0.0
             WHEN project_department_lc <> '' AND (project_department_lc CONTAINS course_lc OR course_lc CONTAINS project_department_lc) THEN 20.0
             ELSE 0.0
         END AS course_score,
         CASE
             WHEN cgpa >= 9.0 THEN 20.0
             WHEN cgpa >= 8.0 THEN 16.0
             WHEN cgpa >= 7.0 THEN 12.0
             WHEN cgpa >= 6.0 THEN 6.0
             ELSE 2.0
         END AS cgpa_score,
         [tag IN tag_names WHERE toLower(coalesce(tag, '')) <> '' AND topic_lc CONTAINS toLower(tag)] AS overlap_topics
    WITH p, overlap_topics, topic_score + course_score + cgpa_score AS score
    RETURN {
        match_type: 'project',
        match_id: p.id,
        match_name: p.title,
        department: p.department,
        score: score,
        reason: 'Project scope best fits your interest and course context.',
        overlap_topics: overlap_topics[0..5],
        required_course: null,
        project_status: p.status,
        project_progress: p.progress
    } AS candidate
}
WITH candidate
ORDER BY candidate.score DESC
RETURN candidate
LIMIT 1
"""


class RecommendationEngine:
    def __init__(self, db: Neo4jClient | None = None) -> None:
        self.db = db or Neo4jClient()

    def recommend_collaborators(self, user_id: str, limit: int = 3) -> list[dict[str, Any]]:
        return self.db.run(COLLABORATOR_QUERY, {"user_id": user_id, "limit": limit})

    def innovation_hotspots(self, years: int = 2) -> list[dict[str, Any]]:
        return self.db.run(HOTSPOT_QUERY, {"years": years})

    def single_student_match(self, topic: str, cgpa: float, course: str) -> dict[str, Any] | None:
        rows = self.db.run(
            STUDENT_SINGLE_MATCH_QUERY,
            {
                "topic": topic,
                "cgpa": cgpa,
                "course": course,
            },
        )
        if rows:
            return rows[0].get("candidate")

        dataset_path = Path("/Users/ashutoshpandey/Downloads/dataset_200.json")
        if not dataset_path.exists():
            return None

        with dataset_path.open("r", encoding="utf-8") as dataset_file:
            payload = json.load(dataset_file)

        topic_lc = topic.strip().lower()
        course_lc = course.strip().lower()

        best: dict[str, Any] | None = None
        best_score = -1.0

        for faculty in payload.get("nodes", {}).get("faculty", []):
            bio = str(faculty.get("bio", ""))
            department = str(faculty.get("department", ""))
            text = f"{bio} {department}".lower()

            topic_score = 60.0 if topic_lc and topic_lc in text else 0.0
            course_score = 20.0 if course_lc and course_lc in department.lower() else 0.0
            cgpa_score = 20.0 if cgpa >= 8 else 12.0 if cgpa >= 7 else 6.0
            total_score = topic_score + course_score + cgpa_score

            if total_score > best_score:
                best_score = total_score
                best = {
                    "match_type": "faculty",
                    "match_id": faculty.get("id"),
                    "match_name": faculty.get("name"),
                    "department": faculty.get("department"),
                    "score": total_score,
                    "reason": "Matched from dataset profile similarity.",
                    "overlap_topics": [topic] if topic_score > 0 else [],
                    "required_course": None,
                    "project_status": None,
                    "project_progress": None,
                }

        for project in payload.get("nodes", {}).get("projects", []):
            title = str(project.get("title", ""))
            description = str(project.get("description", ""))
            tags = [str(tag) for tag in project.get("tags", [])]
            text = f"{title} {description} {' '.join(tags)}".lower()

            topic_score = 65.0 if topic_lc and topic_lc in text else 0.0
            course_score = 0.0
            cgpa_score = 20.0 if cgpa >= 8 else 12.0 if cgpa >= 7 else 6.0
            total_score = topic_score + course_score + cgpa_score

            if total_score > best_score:
                overlap = [tag for tag in tags if topic_lc and topic_lc in tag.lower()]
                best_score = total_score
                best = {
                    "match_type": "project",
                    "match_id": project.get("id"),
                    "match_name": project.get("title"),
                    "department": None,
                    "score": total_score,
                    "reason": "Matched from dataset project relevance.",
                    "overlap_topics": overlap[0:5] if overlap else ([topic] if topic_score > 0 else []),
                    "required_course": None,
                    "project_status": project.get("status"),
                    "project_progress": None,
                }

        return best