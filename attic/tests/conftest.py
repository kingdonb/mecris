# Retired tests, kept for history (#348). Never collect them: some act at import
# time against live services (one sends a real WhatsApp message, one posts a
# Beeminder datapoint). Live tests belong in tests/ behind an explicit opt-in.
collect_ignore_glob = ["test_*.py"]
