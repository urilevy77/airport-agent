from fastapi.testclient import TestClient

from server.app import create_app


def test_app_starts_without_a_frontend_build(tmp_path):
    """A missing dist/ must not break the API — CI has no build."""
    app = create_app(conversation_factory=object, static_dir=tmp_path / "nope")
    client = TestClient(app)
    assert client.get("/health").status_code == 200


def test_serves_the_built_index_at_root(tmp_path):
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>Airport</title>")

    client = TestClient(create_app(conversation_factory=object, static_dir=dist))
    response = client.get("/")
    assert response.status_code == 200
    assert "Airport" in response.text
