from __future__ import annotations

import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

from neo4j import GraphDatabase

from app.config import settings
from search_engine import EmbeddingProvider


SKILLS = [
    "Sustainable Polymers",
    "Machine Learning",
    "Bioinformatics",
    "Quantum Computing",
    "Cybersecurity",
    "Renewable Energy",
    "NLP",
    "Data Engineering",
    "Material Science",
    "Robotics",
    "Graph Analytics",
    "Computer Vision",
    "IoT Systems",
    "Synthetic Biology",
    "Climate Modeling",
    "Optimization",
    "Distributed Systems",
    "Digital Twin",
    "Causal Inference",
    "Human-Computer Interaction",
]

DEPARTMENTS = [
    "Chemical Engineering",
    "Computer Science",
    "Electrical Engineering",
    "Biotechnology",
    "Mechanical Engineering",
]


def _rand_date(last_years: int = 4) -> str:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=365 * last_years)
    delta_days = (now - start).days
    return (start + timedelta(days=random.randint(0, delta_days))).date().isoformat()


def _project_text(title: str, tags: list[str], dept: str) -> str:
    return f"{title}. Tags: {', '.join(tags)}. Department: {dept}."


def _pub_text(title: str, tags: list[str], year: int) -> str:
    return f"{title}. Topics: {', '.join(tags)}. Year: {year}."


def ingest_dummy_data(seed: int = 42, include_embeddings: bool = False) -> dict:
    random.seed(seed)
    embedder = EmbeddingProvider()

    faculty = [
        {
            "id": f"FAC-{i:03d}",
            "name": f"Faculty {i}",
            "department": random.choice(DEPARTMENTS),
            "email": f"faculty{i}@institution.edu",
        }
        for i in range(1, 16)
    ]
    students = [
        {"id": f"STU-{i:03d}", "name": f"Student {i}", "program": random.choice(["MS", "PhD"])}
        for i in range(1, 26)
    ]
    projects = [
        {
            "id": f"PRJ-{i:03d}",
            "title": f"Project {i} on {random.choice(SKILLS)}",
            "description": f"Research initiative focused on {random.choice(SKILLS)} with institutional collaboration.",
            "tags": random.sample(SKILLS, k=3),
            "status": random.choice(["In Progress", "Completed", "Planned"]),
            "progress": random.randint(25, 100),
            "created_at": _rand_date(),
        }
        for i in range(1, 21)
    ]
    publications = [
        {
            "id": f"PUB-{i:03d}",
            "title": f"Publication {i}: Advances in {random.choice(SKILLS)}",
            "tags": random.sample(SKILLS, k=3),
            "year": random.randint(datetime.now().year - 4, datetime.now().year),
            "published_at": _rand_date(),
        }
        for i in range(1, 21)
    ]
    skills = [{"id": f"SKL-{i:03d}", "name": s} for i, s in enumerate(SKILLS, start=1)]

    project_rows: list[dict] = []
    project_student_edges: list[dict] = []
    project_texts: list[str] = []
    for p in projects:
        owner = random.choice(faculty)
        project_rows.append({**p, "owner_id": owner["id"]})
        project_texts.append(_project_text(p["title"], p["tags"], owner["department"]))
        for student in random.sample(students, k=random.randint(1, 3)):
            project_student_edges.append({"sid": student["id"], "pid": p["id"]})

    publication_rows: list[dict] = []
    publication_texts: list[str] = []
    authored_edges_faculty: list[dict] = []
    authored_edges_student: list[dict] = []
    for pub in publications:
        publication_rows.append({**pub})
        publication_texts.append(_pub_text(pub["title"], pub["tags"], pub["year"]))
        for author in random.sample(faculty + students, k=random.randint(1, 3)):
            edge = {"aid": author["id"], "pid": pub["id"]}
            if author["id"].startswith("FAC"):
                authored_edges_faculty.append(edge)
            else:
                authored_edges_student.append(edge)

    if include_embeddings:
        project_embeddings = embedder.embed_texts(project_texts)
        publication_embeddings = embedder.embed_texts(publication_texts)
        for idx, emb in enumerate(project_embeddings):
            project_rows[idx]["embedding"] = emb
        for idx, emb in enumerate(publication_embeddings):
            publication_rows[idx]["embedding"] = emb

    person_dept_rows_faculty: list[dict] = []
    person_dept_rows_student: list[dict] = []
    skill_edges_faculty: list[dict] = []
    skill_edges_student: list[dict] = []
    for person in faculty + students:
        dept = random.choice(DEPARTMENTS)
        dept_row = {"pid": person["id"], "department": dept}
        picked_skills = random.sample(skills, k=random.randint(2, 4))
        for sk in picked_skills:
            edge = {"pid": person["id"], "sid": sk["id"]}
            if person["id"].startswith("FAC"):
                skill_edges_faculty.append(edge)
            else:
                skill_edges_student.append(edge)

        if person["id"].startswith("FAC"):
            person_dept_rows_faculty.append(dept_row)
        else:
            person_dept_rows_student.append(dept_row)

    with GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)) as driver:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                """
                UNWIND $rows AS row
                MERGE (n:Faculty {id: row.id})
                SET n.name = row.name, n.department = row.department, n.email = row.email
                """,
                {"rows": faculty},
            )
            session.run(
                """
                UNWIND $rows AS row
                MERGE (n:Student {id: row.id})
                SET n.name = row.name, n.program = row.program
                """,
                {"rows": students},
            )
            session.run(
                """
                UNWIND $rows AS row
                MERGE (n:Skill {id: row.id})
                SET n.name = row.name
                """,
                {"rows": skills},
            )

            if include_embeddings:
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (n:ResearchProject {id: row.id})
                    SET n.title = row.title,
                        n.description = row.description,
                        n.tags = row.tags,
                        n.status = row.status,
                        n.progress = row.progress,
                        n.created_at = date(row.created_at),
                        n.embedding = row.embedding
                    """,
                    {"rows": project_rows},
                )
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (n:Publication {id: row.id})
                    SET n.title = row.title,
                        n.tags = row.tags,
                        n.year = row.year,
                        n.published_at = date(row.published_at),
                        n.embedding = row.embedding
                    """,
                    {"rows": publication_rows},
                )
            else:
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (n:ResearchProject {id: row.id})
                    SET n.title = row.title,
                        n.description = row.description,
                        n.tags = row.tags,
                        n.status = row.status,
                        n.progress = row.progress,
                        n.created_at = date(row.created_at)
                    """,
                    {"rows": project_rows},
                )
                session.run(
                    """
                    UNWIND $rows AS row
                    MERGE (n:Publication {id: row.id})
                    SET n.title = row.title,
                        n.tags = row.tags,
                        n.year = row.year,
                        n.published_at = date(row.published_at)
                    """,
                    {"rows": publication_rows},
                )

            session.run(
                """
                UNWIND $rows AS row
                MATCH (f:Faculty {id: row.owner_id}), (p:ResearchProject {id: row.id})
                MERGE (f)-[:WORKS_ON]->(p)
                """,
                {"rows": project_rows},
            )
            session.run(
                """
                UNWIND $rows AS row
                MATCH (s:Student {id: row.sid}), (p:ResearchProject {id: row.pid})
                MERGE (s)-[:WORKS_ON]->(p)
                """,
                {"rows": project_student_edges},
            )

            session.run(
                """
                UNWIND $rows AS row
                MATCH (a:Faculty {id: row.aid}), (p:Publication {id: row.pid})
                MERGE (a)-[:AUTHORED]->(p)
                """,
                {"rows": authored_edges_faculty},
            )
            session.run(
                """
                UNWIND $rows AS row
                MATCH (a:Student {id: row.aid}), (p:Publication {id: row.pid})
                MERGE (a)-[:AUTHORED]->(p)
                """,
                {"rows": authored_edges_student},
            )

            session.run(
                """
                UNWIND $rows AS row
                MATCH (p:Faculty {id: row.pid}), (s:Skill {id: row.sid})
                MERGE (p)-[:HAS_SKILL]->(s)
                """,
                {"rows": skill_edges_faculty},
            )
            session.run(
                """
                UNWIND $rows AS row
                MATCH (p:Student {id: row.pid}), (s:Skill {id: row.sid})
                MERGE (p)-[:HAS_SKILL]->(s)
                """,
                {"rows": skill_edges_student},
            )

            session.run(
                """
                UNWIND $rows AS row
                MATCH (p:Faculty {id: row.pid})
                SET p.department = row.department
                MERGE (d:Department {name: row.department})
                MERGE (p)-[:AFFILIATED_WITH]->(d)
                """,
                {"rows": person_dept_rows_faculty},
            )
            session.run(
                """
                UNWIND $rows AS row
                MATCH (p:Student {id: row.pid})
                SET p.department = row.department
                MERGE (d:Department {name: row.department})
                MERGE (p)-[:AFFILIATED_WITH]->(d)
                """,
                {"rows": person_dept_rows_student},
            )

    return {
        "faculty": len(faculty),
        "students": len(students),
        "projects": len(projects),
        "publications": len(publications),
        "skills": len(skills),
        "total_nodes": len(faculty) + len(students) + len(projects) + len(publications) + len(skills),
        "include_embeddings": include_embeddings,
    }


if __name__ == "__main__":
    result = ingest_dummy_data()
    print(result)


def ingest_dataset_json(file_path: str) -> dict:
    dataset_path = Path(file_path).expanduser()
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_path}")

    with dataset_path.open("r", encoding="utf-8") as dataset_file:
        payload = json.load(dataset_file)

    nodes = payload.get("nodes", {})
    edges = payload.get("edges", {})

    faculty_rows = nodes.get("faculty", [])
    student_rows = nodes.get("students", [])
    project_rows = nodes.get("projects", [])
    publication_rows = nodes.get("publications", [])
    skill_rows = nodes.get("skills", [])

    works_on_edges = edges.get("works_on", [])
    authored_edges = edges.get("authored", [])
    has_skill_edges = edges.get("has_skill", [])
    affiliated_edges = edges.get("affiliated", [])

    with GraphDatabase.driver(settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)) as driver:
        with driver.session(database=settings.neo4j_database) as session:
            session.run(
                """
                UNWIND $rows AS row
                MERGE (f:Faculty {id: row.id})
                SET f.name = row.name,
                    f.department = row.department,
                    f.email = row.email,
                    f.bio = row.bio
                """,
                {"rows": faculty_rows},
            )

            session.run(
                """
                UNWIND $rows AS row
                MERGE (s:Student {id: row.id})
                SET s.name = row.name,
                    s.program = row.program,
                    s.email = row.email,
                    s.expected_grad = row.expected_grad
                """,
                {"rows": student_rows},
            )

            session.run(
                """
                UNWIND $rows AS row
                MERGE (p:ResearchProject {id: row.id})
                SET p.title = row.title,
                    p.description = row.description,
                    p.tags = coalesce(row.tags, []),
                    p.created_at = CASE WHEN row.created_at IS NULL THEN p.created_at ELSE date(row.created_at) END,
                    p.status = row.status,
                    p.owner_id = row.owner_id
                """,
                {"rows": project_rows},
            )

            session.run(
                """
                UNWIND $rows AS row
                MERGE (p:Publication {id: row.id})
                SET p.title = row.title,
                    p.abstract = row.abstract,
                    p.tags = coalesce(row.tags, []),
                    p.year = row.year,
                    p.published_at = CASE WHEN row.published_at IS NULL THEN p.published_at ELSE date(row.published_at) END,
                    p.venue = row.venue,
                    p.author_ids = coalesce(row.author_ids, [])
                """,
                {"rows": publication_rows},
            )

            session.run(
                """
                UNWIND $rows AS row
                MERGE (s:Skill {id: row.id})
                SET s.name = row.name,
                    s.category = row.category
                """,
                {"rows": skill_rows},
            )

            session.run(
                """
                UNWIND $rows AS row
                MATCH (person {id: row.person_id})
                MATCH (project:ResearchProject {id: row.project_id})
                WHERE person:Faculty OR person:Student
                MERGE (person)-[:WORKS_ON]->(project)
                """,
                {"rows": works_on_edges},
            )

            session.run(
                """
                UNWIND $rows AS row
                MATCH (person {id: row.person_id})
                MATCH (pub:Publication {id: row.publication_id})
                WHERE person:Faculty OR person:Student
                MERGE (person)-[:AUTHORED]->(pub)
                """,
                {"rows": authored_edges},
            )

            session.run(
                """
                UNWIND $rows AS row
                MATCH (person {id: row.person_id})
                MATCH (skill:Skill {id: row.skill_id})
                WHERE person:Faculty OR person:Student
                MERGE (person)-[:HAS_SKILL]->(skill)
                """,
                {"rows": has_skill_edges},
            )

            session.run(
                """
                UNWIND $rows AS row
                MATCH (person {id: row.person_id})
                WHERE person:Faculty OR person:Student
                MERGE (d:Department {name: row.department})
                SET person.department = row.department
                MERGE (person)-[:AFFILIATED_WITH]->(d)
                """,
                {"rows": affiliated_edges},
            )

    return {
        "faculty": len(faculty_rows),
        "students": len(student_rows),
        "projects": len(project_rows),
        "publications": len(publication_rows),
        "skills": len(skill_rows),
        "works_on": len(works_on_edges),
        "authored": len(authored_edges),
        "has_skill": len(has_skill_edges),
        "affiliated": len(affiliated_edges),
        "source": str(dataset_path),
    }