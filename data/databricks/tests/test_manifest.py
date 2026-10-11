from scripts.build_manifest import build_manifest
from tests.support import REPO_ROOT


def test_manifest_has_sources_and_hashes():
    data = build_manifest(REPO_ROOT)
    assert data["schema_version"] == "pawl.v1"
    assert "generated_at" in data
    assert isinstance(data.get("sources"), list)
    assert data["sources"]
    for entry in data["sources"]:
        assert "path" in entry
        assert "sha256" in entry
        assert "row_count" in entry
