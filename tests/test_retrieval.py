import sqlite3
from contextlib import contextmanager

import pytest

from app.services import retrieval


class FakeCollection:
    def __init__(self):
        self.records = {}

    def get(self, where, **_kwargs):
        ids = [
            record_id
            for record_id, record in self.records.items()
            if record['metadata']['doc_id'] == where['doc_id']
        ]
        return {'ids': ids, 'metadatas': [self.records[item]['metadata'] for item in ids]}

    def upsert(self, ids, documents, metadatas, embeddings):
        for record_id, document, metadata, embedding in zip(ids, documents, metadatas, embeddings):
            self.records[record_id] = {
                'document': document,
                'metadata': metadata,
                'embedding': embedding,
            }

    def delete(self, ids):
        for record_id in ids:
            self.records.pop(record_id, None)


class FakeEmbedder:
    def encode(self, documents, **_kwargs):
        return EncodedVectors([[float(len(document))] for document in documents])


class EncodedVectors(list):
    def tolist(self):
        return list(self)


class FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def execute(self, *_):
        return None


def test_reingesting_document_removes_stale_chunks_without_removing_other_docs(
    tmp_path, monkeypatch
):
    vector_collection = FakeCollection()
    monkeypatch.setattr(retrieval, 'collection', lambda: vector_collection)
    monkeypatch.setattr(retrieval, 'embedder', lambda: FakeEmbedder())

    @contextmanager
    def fake_connect():
        yield FakeConnection()

    monkeypatch.setattr(retrieval, 'connect', fake_connect)
    metadata = {
        'doc_id': 'policy-one',
        'authority_level': 1,
        'effective_from': '2026-01-01',
    }
    document_path = tmp_path / 'policy.txt'
    document_path.write_text('Old policy. ' * 200, encoding='utf-8')
    retrieval.ingest_file(document_path, metadata)
    old_ids = {
        record_id
        for record_id, record in vector_collection.records.items()
        if record['metadata']['doc_id'] == 'policy-one'
    }
    assert len(old_ids) > 1

    other_path = tmp_path / 'other.txt'
    other_path.write_text('A different document.', encoding='utf-8')
    retrieval.ingest_file(other_path, {**metadata, 'doc_id': 'policy-two'})

    document_path.write_text('Updated policy.', encoding='utf-8')
    retrieval.ingest_file(document_path, metadata)

    updated_records = [
        record
        for record in vector_collection.records.values()
        if record['metadata']['doc_id'] == 'policy-one'
    ]
    assert len(updated_records) == 1
    assert updated_records[0]['document'] == 'Updated policy.'
    assert any(
        record['metadata']['doc_id'] == 'policy-two'
        for record in vector_collection.records.values()
    )


def test_delete_document_removes_file_vectors_source_and_registered_rules(
    tmp_path, monkeypatch
):
    docs_dir = tmp_path / 'documents'
    docs_dir.mkdir()
    document_path = docs_dir / 'policy-one.txt'
    document_path.write_text('Policy text.', encoding='utf-8')
    database = sqlite3.connect(':memory:')
    database.row_factory = sqlite3.Row
    database.executescript(
        """
        CREATE TABLE source_register (doc_id TEXT PRIMARY KEY, filename TEXT NOT NULL);
        CREATE TABLE rule_registry (source_doc_id TEXT NOT NULL);
        INSERT INTO source_register VALUES ('policy-one', 'policy-one.txt');
        INSERT INTO rule_registry VALUES ('policy-one');
        INSERT INTO rule_registry VALUES ('other-policy');
        """
    )
    vector_collection = FakeCollection()
    vector_collection.records['chunk-one'] = {
        'document': 'Policy text.',
        'metadata': {'doc_id': 'policy-one'},
        'embedding': [1.0],
    }
    vector_collection.records['chunk-two'] = {
        'document': 'Other policy.',
        'metadata': {'doc_id': 'other-policy'},
        'embedding': [1.0],
    }

    @contextmanager
    def fake_connect():
        yield database
        database.commit()

    monkeypatch.setattr(retrieval, 'DOCS_DIR', docs_dir)
    monkeypatch.setattr(retrieval, 'collection', lambda: vector_collection)
    monkeypatch.setattr(retrieval, 'connect', fake_connect)

    result = retrieval.delete_document('policy-one')

    assert result == {
        'doc_id': 'policy-one',
        'deleted_chunks': 1,
        'deleted_rules': 1,
        'deleted_file': True,
    }
    assert not document_path.exists()
    assert 'chunk-one' not in vector_collection.records
    assert 'chunk-two' in vector_collection.records
    assert database.execute(
        'SELECT COUNT(*) FROM source_register WHERE doc_id=?', ('policy-one',)
    ).fetchone()[0] == 0
    assert database.execute(
        'SELECT COUNT(*) FROM rule_registry WHERE source_doc_id=?', ('policy-one',)
    ).fetchone()[0] == 0
    assert database.execute(
        'SELECT COUNT(*) FROM rule_registry WHERE source_doc_id=?', ('other-policy',)
    ).fetchone()[0] == 1


def test_delete_document_rejects_registered_path_outside_documents_directory(
    tmp_path, monkeypatch
):
    docs_dir = tmp_path / 'documents'
    docs_dir.mkdir()
    outside_file = tmp_path / 'outside.txt'
    outside_file.write_text('Do not delete.', encoding='utf-8')
    database = sqlite3.connect(':memory:')
    database.row_factory = sqlite3.Row
    database.execute(
        'CREATE TABLE source_register (doc_id TEXT PRIMARY KEY, filename TEXT NOT NULL)'
    )
    database.execute('CREATE TABLE rule_registry (source_doc_id TEXT NOT NULL)')
    database.execute(
        "INSERT INTO source_register VALUES ('policy-one', '../outside.txt')"
    )

    @contextmanager
    def fake_connect():
        yield database

    monkeypatch.setattr(retrieval, 'DOCS_DIR', docs_dir)
    monkeypatch.setattr(retrieval, 'connect', fake_connect)

    with pytest.raises(ValueError, match='outside the documents directory'):
        retrieval.delete_document('policy-one')

    assert outside_file.read_text(encoding='utf-8') == 'Do not delete.'
