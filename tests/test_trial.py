from benchmarks.trial import run


def test_three_episodes_report_counts_only():
    from pathlib import Path

    result = run(Path("benchmarks/episodes"))
    assert result["episodes"] == 3
    assert result["caught"] >= 1
    assert result["false_blocks"] == 0
