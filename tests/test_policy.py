from app.services.policy import choose_precedence


def _hit(doc_id, authority_level, effective_from, **metadata):
    return {
        'metadata': {
            'doc_id': doc_id,
            'authority_level': authority_level,
            'effective_from': effective_from,
            **metadata,
        }
    }


def test_equal_authority_sources_are_not_assumed_to_conflict():
    hits = [
        _hit('RET-TERMS-2026', 1, '2026-01-01'),
        _hit('RET-WARRANTY-2026', 1, '2026-01-01'),
    ]

    chosen, decisions, conflict = choose_precedence(hits, '2026-10-01')

    assert {hit['metadata']['doc_id'] for hit in chosen} == {
        'RET-TERMS-2026',
        'RET-WARRANTY-2026',
    }
    assert not decisions
    assert conflict is False


def test_higher_authority_source_overrides_lower_authority():
    hits = [
        _hit('RET-TERMS-2026', 1, '2026-01-01'),
        _hit('RET-SHIPPING-2026', 4, '2026-01-01'),
    ]

    chosen, decisions, conflict = choose_precedence(hits, '2026-10-01')

    assert [hit['metadata']['doc_id'] for hit in chosen] == ['RET-TERMS-2026']
    assert decisions == ['Authority level 1 overrides lower-authority source']
    assert conflict is False


def test_authoritative_supersession_removes_superseded_source():
    hits = [
        _hit('RET-TERMS-2026', 1, '2026-01-01'),
        _hit('RET-CIRCULAR-2026', 1, '2026-05-01', supersedes='RET-TERMS-2026'),
    ]

    chosen, decisions, conflict = choose_precedence(hits, '2026-10-01')

    assert [hit['metadata']['doc_id'] for hit in chosen] == ['RET-CIRCULAR-2026']
    assert decisions == ['RET-CIRCULAR-2026 supersedes RET-TERMS-2026']
    assert conflict is False
