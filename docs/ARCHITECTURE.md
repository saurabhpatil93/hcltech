# Architecture and design decisions

```text
Streamlit UI -> FastAPI/Pydantic -> LangGraph workflow
                              |-> Sentence Transformers -> persistent ChromaDB (policy RAG)
                              |-> SQLite deterministic tools (orders/returns/rules)
                              |-> Ollama local LLM (grounded wording only)
                              +-> audit records / citations
```

- RAG handles policy/procedure text; citations include document ID, section/chunk, version and effective date.
- SQLite tools are authoritative for order lookup, eligibility, refund arithmetic and warranty dates.
- Source precedence: applicability/effective dates, explicit supersession by authority level 1/2, authority, then recency. Equally authoritative retrieved documents are not assumed to conflict just because they have different document IDs; deterministic rule conflicts are escalated by the SQLite tools.
- LangGraph uses a small fixed workflow rather than multiple agents because the work is mostly deterministic and easier to test.
- ChromaDB persists to disk and is not re-ingested on each restart. Re-ingesting a document replaces its obsolete chunks while preserving other documents.
- Audit includes trace, citations, tools, decisions, model, latency and answer type; it does not log chain-of-thought.

## Demo limitations to disclose
This is not production authentication. X-Customer-Id must be set by a trusted identity gateway in production. Scanned-PDF OCR is not included. Source precedence is a baseline that must be stress-tested against judge documents. Refund is calculated but not executed. Audit question text is truncated but not fully PII-redacted; use synthetic data only.
