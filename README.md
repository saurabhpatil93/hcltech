# Retail AI Support Agent — HCLTech Hackathon

Implements the Retail AI Support Agent case study with RAG plus deterministic retail tools. It follows Annexure C's required SQLite tables: `customers`, `products`, `orders`, `order_items`, `returns`, and `rule_registry`; support tables `source_register` and `audit_records` are additional.

## Stack
Python 3.11, Streamlit, FastAPI, Pydantic v2, LangGraph, persistent ChromaDB, sentence-transformers/all-MiniLM-L6-v2, SQLite, local Ollama, Docker Compose.

## Windows setup
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
ollama pull llama3.1:8b
python scripts/generate_synthetic_data.py
python scripts/validate_data.py --dir data/csv
python -m scripts.init_demo
python -m scripts.load_data --dir data/csv
```
Terminal 1: `uvicorn app.main:app --reload`
Terminal 2: `streamlit run app/ui.py`
Set a strong `ADMIN_PASSWORD` in `.env` before starting the API; there is no built-in default password. The customer interface is at http://localhost:8501; the separate admin page is available at http://localhost:8501/Admin and requires this password. The customer interface accepts a customer ID to scope demo order queries. Indexed documents persist across page changes and application restarts; files selected but not yet ingested are retained only for the current Streamlit browser session.

If you want to test pipeline without Ollama, set `MOCK_LLM=true` in `.env` and restart API. This is only a mock mode, not real LLM generation. First embedding run may download the model.

## Docker
Start Ollama on host then run `docker compose up --build`. If `host.docker.internal` is not resolvable, adjust `OLLAMA_BASE_URL`.

## API
`POST /ask` body `{"question":"What is the return window for electronics?","as_of_date":"2026-10-01"}` with header `X-Customer-Id: C1001`; `POST /ingest` accepts one multipart file and `metadata_json`, while `POST /ingest/batch` accepts repeated `files` fields and a `metadata_json` JSON list with one entry per file. Both ingestion endpoints require `X-Admin-Password`, checked against `ADMIN_PASSWORD`; admin sign-in is verified by `GET /admin/session`. Also available: `GET /health`, `GET /sources`, and `GET /audit/{trace_id}`. Customer ID and the shared admin password are demo credentials, not production authentication. Production must derive customer identity from verified authentication and use an identity provider for admin access.

## Data
Run `python scripts/generate_synthetic_data.py`, validate with `python scripts/validate_data.py --dir data/csv`, load using `python -m scripts.load_data --dir data/csv`. It creates 35 customers, 22 products and 70 orders, including edge cases. Annexure C asks for LLM-generated synthetic data; the bundled generator uses seeded Python, and discloses this. Use an approved LLM and preserve the exact prompt/model/output if strict compliance is required. Never use real customer data.

## Tests
`pytest -q`

## Security and limitations
No real personal data; RAG context is treated as reference data, not instructions; order tools scope queries to the authenticated customer; refund arithmetic is code-based; unresolved policy conflicts should be escalated. This is a hackathon demo, not production identity management or transaction processing. OCR for scanned documents is not bundled. See `docs/`.
