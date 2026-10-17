from pawl.doctor import SKIP_DIR_NAMES, findings


def test_doctor_ignores_virtualenv(tmp_path):
    (tmp_path / ".venv" / "lib").mkdir(parents=True)
    (tmp_path / ".venv" / "lib" / "noise.py").write_text("x = 1\n")
    (tmp_path / "pawl.toml").write_text("[pawl]\n")
    (tmp_path / "pawl.baseline.json").write_text("{}\n")
    text = "\n".join(findings(tmp_path))
    assert ".venv" not in text
    assert "scannable python files: 0" in text


def test_skip_dirs_match_on_any_separator():
    assert ".venv" in SKIP_DIR_NAMES
    assert "site-packages" in SKIP_DIR_NAMES
