CREATE CONSTRAINT student_id_unique IF NOT EXISTS FOR (s:Student) REQUIRE s.id IS UNIQUE;
CREATE CONSTRAINT faculty_id_unique IF NOT EXISTS FOR (f:Faculty) REQUIRE f.id IS UNIQUE;
CREATE CONSTRAINT project_id_unique IF NOT EXISTS FOR (p:ResearchProject) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT publication_id_unique IF NOT EXISTS FOR (p:Publication) REQUIRE p.id IS UNIQUE;
CREATE CONSTRAINT skill_id_unique IF NOT EXISTS FOR (s:Skill) REQUIRE s.id IS UNIQUE;

CREATE INDEX student_name_idx IF NOT EXISTS FOR (s:Student) ON (s.name);
CREATE INDEX faculty_name_idx IF NOT EXISTS FOR (f:Faculty) ON (f.name);
CREATE INDEX project_title_idx IF NOT EXISTS FOR (p:ResearchProject) ON (p.title);
CREATE INDEX publication_title_idx IF NOT EXISTS FOR (p:Publication) ON (p.title);
CREATE INDEX skill_name_idx IF NOT EXISTS FOR (s:Skill) ON (s.name);

CREATE VECTOR INDEX research_entity_embeddings IF NOT EXISTS
FOR (n:ResearchProject|Publication|Faculty|Student)
ON (n.embedding)
OPTIONS {
  indexConfig: {
    `vector.dimensions`: 1536,
    `vector.similarity_function`: 'cosine'
  }
};