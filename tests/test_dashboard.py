from pawl.dashboard import render


def test_message_is_escaped():
    html = render([], [{"message": "<script>"}])
    assert "&lt;script&gt;" in html
    assert "<script>" not in html
