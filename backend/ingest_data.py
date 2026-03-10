from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

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