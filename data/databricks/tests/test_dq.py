from pawl_core.dq import dq_check

def test_gate_result_label_is_quarantined(synthetic_record):
    rec = dict(synthetic_record)
    rec["label_derivation"] = "gate_result"
    assert "DQ_GATE_LABEL_DERIVATION" in dq_check(rec)

def test_model_value_in_human_field_is_quarantined(synthetic_record):
    rec = dict(synthetic_record)
    rec["human_disposition"] = {"label": "TAMPER", "by": "model:foo", "at": "2025-01-01"}
    assert "DQ_HUMAN_LABEL_SOURCE_NOT_HUMAN" in dq_check(rec)

def test_valid_synthetic_record_has_no_failures(synthetic_record):
    assert dq_check(synthetic_record) == []
