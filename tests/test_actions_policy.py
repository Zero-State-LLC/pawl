from pawl.actions_policy import workflow_findings


def test_floating_tag_is_flagged():
    assert workflow_findings("uses: actions/checkout@v4")


def test_sha_pin_is_clean():
    assert workflow_findings("uses: actions/checkout@" + "a" * 40) == []


def test_mixed_file_is_still_flagged():
    text = "uses: actions/checkout@" + "a" * 40 + "\nuses: actions/setup-python@v5\n"
    assert workflow_findings(text)
