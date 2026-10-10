# Architecture and design decisions

```text
Customer/Admin browser -> Streamlit -> FastAPI/Pydantic -> LangGraph workflow
                                                    |-> Sentence Transformers -> persistent ChromaDB (policy RAG)
                                                    |-> SQLite deterministic tools (orders/returns/rules)
                                                    |-> Ollama local LLM (grounded wording only)
                                                    +-> SQLite audit records + data/audit.jsonl
Admin document upload -> FastAPI -> data/documents + ChromaDB + SQLite source registry
```

- RAG handles policy/procedure text; citations include document ID, section/chunk, version and effective date.
- SQLite tools are authoritative for order lookup, eligibility, refund arithmetic and warranty dates.
- `data/source_register.csv` lists the policy sources. `data/rule_registry.csv` lists deterministic rules; each row includes `source_doc_id` and `source_section`, and demo initialization validates each section against the policy text before loading the rules into SQLite.
- SQLite and ChromaDB run in-process with the API; Docker Compose persists them and uploaded files through the `./data:/workspace/data` bind mount. They are not separate database containers.
- Source precedence: applicability/effective dates, explicit supersession by authority level 1/2, authority, then recency. Equally authoritative retrieved documents are not assumed to conflict just because they have different document IDs; deterministic rule conflicts are escalated by the SQLite tools.
- LangGraph uses a small fixed workflow rather than multiple agents because the work is mostly deterministic and easier to test.
- ChromaDB persists to disk and is not re-ingested on each restart. Re-ingesting a document replaces its obsolete chunks while preserving other documents.
- Audit includes trace, citations, tools, decisions, model, latency and answer type; it does not log chain-of-thought.

## Demo limitations to disclose
This is not production authentication. X-Customer-Id must be set by a trusted identity gateway in production. Scanned-PDF OCR is not included. Source precedence is a baseline that must be stress-tested against judge documents. Refund is calculated but not executed. Audit question text is truncated but not fully PII-redacted; use synthetic data only.
