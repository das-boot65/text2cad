from fastapi.testclient import TestClient

from app.main import create_app


def test_chunked_body_limit_and_nonascii_secret(tmp_path):
    with TestClient(create_app(tmp_path, "secret", probe=False)) as client:
        assert client.post("/api/sessions", json={"secret": "漢字"}).status_code == 401
        response = client.post(
            "/api/parse",
            content=iter([b"x" * 40000, b"x" * 40000]),
            headers={"Content-Type": "application/json"},
        )
        assert response.status_code == 413
