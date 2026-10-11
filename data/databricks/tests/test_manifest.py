import json

from tests.conftest import MANIFEST_PATH

def test_manifest_has_sources_and_hashes():
    if not MANIFEST_PATH.exists():
        import pytest
        pytest.skip("manifest absent; run python scripts/build_manifest.py")
    data = json.loads(MANIFEST_PATH.read_text())
    assert data["schema_version"] == "pawl.v1"
    assert "generated_at" in data
    assert isinstance(data.get("sources"), list)
    assert data["sources"]
    for entry in data["sources"]:
        assert "path" in entry
        assert "sha256" in entry
        assert "row_count" in entry
