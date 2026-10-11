import pytest
from pawl_core.split import assert_no_group_crosses, split_for_record
from tests.support import synthetic_record


def test_whole_group_lands_in_one_split():
    records = []
    for i in range(5):
        rec = dict(synthetic_record())
        rec["record_id"] = f"r{i}"
        rec["task"] = dict(rec["task"])
        rec["task"]["task_id"] = "t1"
        rec["task"]["repo_rev"] = "rev1"
        rec["exploit_family"] = "fam"
        records.append(rec)
    splits = {split_for_record(r) for r in records}
    assert len(splits) == 1
    assert_no_group_crosses(records)


def test_group_cross_is_detected():
    a = dict(synthetic_record())
    a["task"] = dict(a["task"])
    a["task"]["task_id"] = "t1"
    a["task"]["repo_rev"] = "rev1"
    a["exploit_family"] = "fam"
    a["split"] = "train"
    b = dict(a)
    b["split"] = "test"
    with pytest.raises(ValueError):
        assert_no_group_crosses([a, b])
