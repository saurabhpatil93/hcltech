from contextlib import contextmanager

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
