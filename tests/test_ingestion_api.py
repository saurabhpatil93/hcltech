import json

import pytest
from fastapi.testclient import TestClient

from app import main


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'ADMIN_PASSWORD', 'test-admin-password')
    monkeypatch.setattr(main, 'DOCS_DIR', tmp_path)
    monkeypatch.setattr(main, 'init_db', lambda: None)
    with TestClient(main.app) as client:
        yield client


def test_admin_session_requires_configured_password(api_client):
    response = api_client.get('/admin/session')

    assert response.status_code == 401


def test_admin_session_fails_closed_when_password_is_not_configured(api_client, monkeypatch):
    monkeypatch.setattr(main, 'ADMIN_PASSWORD', '')

    response = api_client.get('/admin/session', headers={'X-Admin-Password': 'anything'})

    assert response.status_code == 503


def test_batch_ingest_indexes_each_file(api_client, monkeypatch):
    indexed = []

    def fake_ingest_file(path, metadata):
        indexed.append((path.name, metadata['doc_id']))
        return {'doc_id': metadata['doc_id'], 'chunks_indexed': 1, 'status': 'indexed'}

    monkeypatch.setattr(main, 'ingest_file', fake_ingest_file)
    files = [
        ('files', ('returns.txt', b'return policy', 'text/plain')),
        ('files', ('warranty.md', b'warranty policy', 'text/markdown')),
    ]
    metadata = [
        {'doc_id': 'RETURNS-2026', 'authority_level': 1, 'effective_from': '2026-01-01'},
        {'doc_id': 'WARRANTY-2026', 'authority_level': 1, 'effective_from': '2026-01-01'},
    ]

    response = api_client.post(
        '/ingest/batch',
        headers={'X-Admin-Password': 'test-admin-password'},
        files=files,
        data={'metadata_json': json.dumps(metadata)},
    )

    assert response.status_code == 200
    assert response.json()['succeeded'] == 2
    assert response.json()['failed'] == 0
    assert indexed == [('RETURNS-2026.txt', 'RETURNS-2026'), ('WARRANTY-2026.md', 'WARRANTY-2026')]


def test_batch_ingest_requires_one_metadata_entry_per_file(api_client):
    response = api_client.post(
        '/ingest/batch',
        headers={'X-Admin-Password': 'test-admin-password'},
        files=[('files', ('returns.txt', b'return policy', 'text/plain'))],
        data={'metadata_json': json.dumps([])},
    )

    assert response.status_code == 422


def test_batch_ingest_rejects_path_traversal_doc_id(api_client):
    metadata = [{'doc_id': '../outside', 'authority_level': 1, 'effective_from': '2026-01-01'}]

    response = api_client.post(
        '/ingest/batch',
        headers={'X-Admin-Password': 'test-admin-password'},
        files=[('files', ('returns.txt', b'return policy', 'text/plain'))],
        data={'metadata_json': json.dumps(metadata)},
    )

    assert response.status_code == 422
