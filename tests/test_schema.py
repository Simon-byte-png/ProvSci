from provsci.schema import WHITELIST_TOOLS, ResultCard


def test_whitelist_is_small_and_deterministic() -> None:
    assert "arith_eval" in WHITELIST_TOOLS
    assert "unit_convert" in WHITELIST_TOOLS
    assert len(WHITELIST_TOOLS) == 7


def test_result_card_keys() -> None:
    card: ResultCard = {
        "id": "demo-001",
        "question": "IC50 是多少？",
        "answer": "12.5",
        "unit": "nM",
        "conditions": ["24 h"],
        "task_kind": "lookup",
        "evidence": [
            {
                "doi": "10.0000/demo",
                "page": 4,
                "table_id": "Table 1",
                "row": 2,
                "col": 3,
                "quote": "12.5 nM",
            }
        ],
        "path": [{"tool": "extract_table_cell", "args": {"table": "Table 1", "row": 2, "col": 3}, "output": "12.5 nM"}],
        "verified": False,
        "verifier_value": None,
        "tolerance": "1e-6",
        "license": "CC-BY",
        "quality": "raw",
        "notes": [],
    }
    assert card["quality"] == "raw"
