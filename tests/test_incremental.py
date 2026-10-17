from pawl.check import incremental_usable


def test_fresh_matching_report_is_usable():
    assert incremental_usable(
        report_mtime=1_000.0, now=3_600.0, collected=10, baseline_collected=10
    )


def test_stale_report_is_not_usable():
    assert not incremental_usable(
        report_mtime=0.0, now=90_000.0, collected=10, baseline_collected=10
    )


def test_count_mismatch_is_not_usable():
    assert not incremental_usable(
        report_mtime=1_000.0, now=2_000.0, collected=11, baseline_collected=10
    )
