from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional
import hmac, json, re, uuid, time
from app.config import ADMIN_PASSWORD, DOCS_DIR, OLLAMA_BASE_URL, OLLAMA_MODEL, MOCK_LLM, AUDIT_PATH
from app.db import init_db, connect
from app.schemas import AskRequest, AskResponse, HealthResponse
from app.services.retrieval import delete_document, ingest_file, collection
from app.graph import assistant_graph

app = FastAPI(title='Retail AI Support Agent', version='1.0.0')

SUPPORTED_DOCUMENT_TYPES = {'.pdf', '.docx', '.txt', '.md'}
DOC_ID_PATTERN = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,99}\Z')


@app.on_event('startup')
def startup():
    init_db()
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def require_admin(password: Optional[str]) -> None:
    if not ADMIN_PASSWORD:
        raise HTTPException(503, 'Admin ingestion is disabled; configure ADMIN_PASSWORD.')
    if not password or not hmac.compare_digest(password, ADMIN_PASSWORD):
        raise HTTPException(401, 'Valid admin password required.')


def validate_ingest_metadata(metadata, filename):
    if not isinstance(metadata, dict):
        raise HTTPException(422, 'Each metadata entry must be a JSON object.')
    if not all(key in metadata for key in ('doc_id', 'authority_level', 'effective_from')):
        raise HTTPException(422, 'Required metadata: doc_id, authority_level, effective_from')
    doc_id = str(metadata['doc_id'])
    if not DOC_ID_PATTERN.fullmatch(doc_id):
        raise HTTPException(422, 'doc_id must start with a letter or digit and contain only letters, digits, ".", "_" or "-".')
    try:
        int(metadata['authority_level'])
        date.fromisoformat(str(metadata['effective_from']))
    except (TypeError, ValueError):
        raise HTTPException(422, 'authority_level must be an integer and effective_from must be an ISO date.')
    ext = Path(filename or '').suffix.lower()
    if ext not in SUPPORTED_DOCUMENT_TYPES:
        raise HTTPException(415, 'Supported files: PDF, DOCX, TXT, MD')
    return doc_id, ext


async def ingest_upload(file: UploadFile, metadata: dict, doc_id: str, extension: str):
    target = DOCS_DIR / (doc_id + extension)
    target.write_bytes(await file.read())
    return ingest_file(target, metadata)


def audit_record(r):
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open('a', encoding='utf-8') as f:
        f.write(json.dumps(r, default=str) + '\n')
    with connect() as c:
        c.execute('INSERT OR REPLACE INTO audit_records VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                  (r['trace_id'], r['timestamp'], r.get('customer_id'), r.get('question_category'),
                   r.get('question_redacted'), json.dumps(r.get('sources_retrieved', [])),
                   json.dumps(r.get('precedence_decisions', [])), json.dumps(r.get('tools_invoked', [])),
                   r['answer_type'], r.get('model'), r['latency_ms'], json.dumps(r, default=str)))


@app.get('/')
def root():
    return {'name': 'Retail AI Support Agent', 'docs': '/docs', 'health': '/health'}


@app.get('/health', response_model=HealthResponse)
def health():
    try:
        with connect() as c:
            c.execute('SELECT 1')
        sql = 'ok'
    except Exception:
        sql = 'error'
    try:
        vec = 'ok' if collection().count() >= 0 else 'error'
    except Exception:
        vec = 'error'
    if MOCK_LLM:
        llm = 'mock mode'
    else:
        try:
            import ollama
            ollama.Client(host=OLLAMA_BASE_URL).list()
            llm = 'available: ' + OLLAMA_MODEL
        except Exception:
            llm = 'unavailable: ' + OLLAMA_MODEL
    return {'status': 'ok' if sql == 'ok' and vec == 'ok' and (llm.startswith('available') or llm == 'mock mode') else 'degraded',
            'sqlite': sql, 'vector_store': vec, 'llm': llm}


@app.get('/admin/session')
def admin_session(x_admin_password: Optional[str] = Header(default=None, alias='X-Admin-Password')):
    require_admin(x_admin_password)
    return {'authenticated': True}


@app.post('/ask', response_model=AskResponse)
def ask(body: AskRequest, x_customer_id: Optional[str] = Header(default=None, alias='X-Customer-Id')):
    start = time.time()
    asof = (body.as_of_date or date.today()).isoformat()
    tier = 'STANDARD'
    if x_customer_id:
        with connect() as c:
            r = c.execute('SELECT tier FROM customers WHERE customer_id=?', (x_customer_id,)).fetchone()
        if r:
            tier = r['tier']
    state = assistant_graph.invoke({'question': body.question, 'customer_id': x_customer_id,
                                    'as_of_date': asof, 'tier': tier})
    trace = uuid.uuid4().hex[:12]
    cites = [{'doc_id': h['metadata'].get('doc_id'), 'section': h['metadata'].get('section'),
              'version': h['metadata'].get('version'), 'effective_from': h['metadata'].get('effective_from'),
              'effective_to': h['metadata'].get('effective_to'), 'distance': round(h.get('distance', 0), 4)}
             for h in state.get('chosen', [])]
    tools = [{'tool': 'retail_tool_router', 'status': 'invoked', 'output': state['tool_result']}] if state.get('tool_result') else []
    rec = {'trace_id': trace, 'timestamp': datetime.now(timezone.utc).isoformat(),
           'customer_id': x_customer_id, 'question_category': 'GENERAL',
           'question_redacted': body.question[:250], 'sources_retrieved': cites,
           'precedence_decisions': state.get('decisions', []), 'tools_invoked': tools,
           'answer_type': state.get('answer_type', 'not_found'),
           'model': 'mock' if MOCK_LLM else OLLAMA_MODEL,
           'latency_ms': int((time.time() - start) * 1000), 'answer': state.get('answer', '')}
    audit_record(rec)
    return {'trace_id': trace, 'answer': rec['answer'], 'answer_type': rec['answer_type'],
            'citations': cites, 'tools_invoked': tools, 'as_of_date': asof}


@app.post('/ingest')
async def ingest(file: UploadFile = File(...), metadata_json: str = Form(...),
                 x_admin_password: Optional[str] = Header(default=None, alias='X-Admin-Password')):
    require_admin(x_admin_password)
    try:
        m = json.loads(metadata_json)
    except json.JSONDecodeError:
        raise HTTPException(400, 'metadata_json must be valid JSON')
    doc_id, ext = validate_ingest_metadata(m, file.filename)
    try:
        return await ingest_upload(file, m, doc_id, ext)
    except Exception as e:
        raise HTTPException(500, f'Ingestion failed: {type(e).__name__}: {e}')


@app.post('/ingest/batch')
async def ingest_batch(files: list[UploadFile] = File(...), metadata_json: str = Form(...),
                       x_admin_password: Optional[str] = Header(default=None, alias='X-Admin-Password')):
    require_admin(x_admin_password)
    try:
        metadata_entries = json.loads(metadata_json)
    except json.JSONDecodeError:
        raise HTTPException(400, 'metadata_json must be valid JSON.')
    if not isinstance(metadata_entries, list) or len(metadata_entries) != len(files):
        raise HTTPException(422, 'metadata_json must be a list with one metadata object per uploaded file.')

    validated = []
    doc_ids = set()
    for file, metadata in zip(files, metadata_entries):
        doc_id, extension = validate_ingest_metadata(metadata, file.filename)
        if doc_id in doc_ids:
            raise HTTPException(422, f'Duplicate doc_id in batch: {doc_id}')
        doc_ids.add(doc_id)
        validated.append((file, metadata, doc_id, extension))

    results = []
    for file, metadata, doc_id, extension in validated:
        try:
            result = await ingest_upload(file, metadata, doc_id, extension)
            results.append({'doc_id': doc_id, 'filename': file.filename, 'status': 'indexed', **result})
        except Exception as e:
            results.append({'doc_id': doc_id, 'filename': file.filename, 'status': 'error',
                            'error': f'{type(e).__name__}: {e}'})
    failed = sum(result['status'] == 'error' for result in results)
    return {'results': results, 'succeeded': len(results) - failed, 'failed': failed}


@app.get('/sources')
def sources():
    with connect() as c:
        rows = c.execute('SELECT * FROM source_register ORDER BY effective_from DESC').fetchall()
    return {'sources': [dict(r) for r in rows]}


@app.delete('/sources/{doc_id}')
def remove_source(doc_id: str,
                  x_admin_password: Optional[str] = Header(default=None, alias='X-Admin-Password')):
    require_admin(x_admin_password)
    if not DOC_ID_PATTERN.fullmatch(doc_id):
        raise HTTPException(422, 'Invalid document ID.')
    try:
        return delete_document(doc_id)
    except FileNotFoundError:
        raise HTTPException(404, 'Document not found.')


@app.get('/audit/{trace_id}')
def get_audit(trace_id: str, x_customer_id: Optional[str] = Header(default=None, alias='X-Customer-Id'),
              x_admin: Optional[str] = Header(default=None, alias='X-Admin')):
    with connect() as c:
        r = c.execute('SELECT * FROM audit_records WHERE trace_id=?', (trace_id,)).fetchone()
    if not r:
        raise HTTPException(404, 'Audit record not found')
    if x_admin != 'true' and r['customer_id'] != x_customer_id:
        raise HTTPException(403, 'Audit visible only to requesting customer or admin')
    return json.loads(r['response_json'])