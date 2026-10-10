# Evaluation plan

Run `python scripts/validate_data.py --dir data/csv` and `pytest -q`. Evaluate paraphrases for: cited policy fact; order lookup; cross-customer access denial; last day and one day after return window; non-returnable category; discounted refund; high refund approval; valid/expired warranty; future-effective circular; supersession; unresolved conflict; prompt injection in delivery notes; unknown question; and live ingestion. Record expected/actual, pass/fail, citation correctness, answer type and latency. Do not claim a score until measured.
