# Institutional Knowledge Intelligence Engine

Production-oriented starter stack for institutional knowledge intelligence using:

- FastAPI backend
- Neo4j graph database
- LangChain + OpenAI embeddings (`text-embedding-3-small`) with SentenceTransformers fallback
- Hybrid Cypher + vector search
- React + Tailwind frontend scaffold

## Quick Start

1. Copy environment values:

```bash
cp backend/.env.example backend/.env
```

2. Start services:

```bash
docker compose up --build
```

3. Initialize schema and ingest dummy data:

```bash
curl -X POST http://localhost:8000/admin/init-schema
curl -X POST http://localhost:8000/admin/ingest-dummy
```

4. Try semantic search:

```bash
curl "http://localhost:8000/search/researchers?query=Who%20is%20working%20on%20sustainable%20polymers%3F"
```

## Structure

- `docker-compose.yml`
- `backend/schema.py`
- `backend/ingest_data.py`
- `backend/search_engine.py`
- `backend/recommendation_engine.py`
- `backend/app/main.py`

## Notes

- Pinecone integration is optional via environment variables.
- If OpenAI API key is missing, the system falls back to SentenceTransformers local embeddings.# Knowledge-Graph
