import csv
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from scripts import init_demo
from scripts.validate_data import validate


def test_dataset():
    errors, counts = validate('data/csv')
    assert not errors, errors
    assert counts['customers'] >= 30
    assert counts['products'] >= 20
    assert counts['orders'] >= 60


def test_rule_registry_entries_cite_sections_in_registered_sources():
    root = Path(__file__).resolve().parents[1]
    with (root / 'data/source_register.csv').open(
        newline='', encoding='utf-8-sig'
    ) as file:
        source_rows = list(csv.DictReader(file))
    with (root / 'data/rule_registry.csv').open(
        newline='', encoding='utf-8-sig'
    ) as file:
        rule_rows = list(csv.DictReader(file))

    sources_by_id = {source['doc_id']: source for source in source_rows}
    init_demo.validate_rule_citations(rule_rows, sources_by_id)


def test_rule_registry_seed_persists_rules_with_source_citations(monkeypatch):
    root = Path(__file__).resolve().parents[1]
    with (root / 'data/source_register.csv').open(
        newline='', encoding='utf-8-sig'
    ) as file:
        source_rows = list(csv.DictReader(file))
    with (root / 'data/rule_registry.csv').open(
        newline='', encoding='utf-8-sig'
    ) as file:
        rule_rows = list(csv.DictReader(file))

    database = sqlite3.connect(':memory:')
    database.executescript(
        """
        CREATE TABLE source_register (doc_id TEXT PRIMARY KEY);
        CREATE TABLE rule_registry (
            rule_id TEXT PRIMARY KEY, description TEXT, parameter TEXT,
            operator TEXT, value TEXT, scope_categories TEXT, scope_tiers TEXT,
            effective_from TEXT, effective_to TEXT, source_doc_id TEXT,
            source_section TEXT
        );
        """
    )
    database.executemany(
        'INSERT INTO source_register (doc_id) VALUES (?)',
        [(source['doc_id'],) for source in source_rows],
    )

    @contextmanager
    def fake_connect():
        yield database
        database.commit()

    monkeypatch.setattr(init_demo, 'connect', fake_connect)
    init_demo.persist_rule_registry(rule_rows)

    rows = database.execute(
        'SELECT source_doc_id, source_section FROM rule_registry'
    ).fetchall()
    assert len(rows) == len(rule_rows)
    assert all(source_id and section for source_id, section in rows)
