import io
import time
import zipfile

from fastapi.testclient import TestClient

from app.main import create_app

PROMPT = (
    "Make a 60 x 25 mm base plate, 5 mm thick, with four 4.5 mm clearance holes spaced 40 x 15 mm."
)


def wait_for_job(client, auth, job):
    deadline = time.monotonic() + 70
    while time.monotonic() < deadline:
        current = client.get("/api/jobs/" + job["id"], headers=auth).json()
        if current["state"] in ("completed", "failed", "cancelled"):
            return current
        time.sleep(0.05)
    raise AssertionError("CAD job failed to reach a terminal state")


def test_real_parse_confirm_generate_export_revision_pipeline(tmp_path):
    with TestClient(create_app(tmp_path, "secret")) as client:
        assert client.get("/api/health").json()["ready"]
        assert client.post("/api/projects", json={"name": "Demo"}).status_code == 401
        login = client.post("/api/sessions", json={"secret": "secret"}).json()
        auth = {"Authorization": "Bearer " + login["token"]}
        parsed = client.post("/api/parse", headers=auth, json={"text": PROMPT}).json()
        assert parsed["status"] == "ready"
        project = client.post("/api/projects", headers=auth, json={"name": "Demo"}).json()
        revision = client.post(
            f"/api/projects/{project['id']}/revisions",
            headers=auth,
            json={"spec": parsed["parsed_spec"], "parent_id": None, "confirmed": True},
        ).json()
        assert "id" in revision
        assert (
            client.post(
                f"/api/projects/{project['id']}/revisions",
                headers=auth,
                json={"spec": parsed["parsed_spec"], "parent_id": None, "confirmed": True},
            ).status_code
            == 409
        )
        job = client.post(f"/api/revisions/{revision['id']}/generate", headers=auth, json={}).json()
        result = wait_for_job(client, auth, job)
        assert result["state"] == "completed", result
        assert result["worker_exit_code"] == 0
        assert result["validation"]["valid"]
        assert result["validation"]["bbox_mm"] == [60, 25, 5]
        assert len(result["artifacts"]) == 4
        assert client.get(f"/api/revisions/{revision['id']}/downloads/step").status_code == 401
        response = client.get(f"/api/revisions/{revision['id']}/handoff", headers=auth)
        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            assert {
                "model.step",
                "model.stl",
                "spec.json",
                "validation_report.json",
                "revision_history.json",
            }.issubset(archive.namelist())
            assert login["token"].encode() not in archive.read("generation_metadata.json")
        change = client.post(
            "/api/parse",
            headers=auth,
            json={"text": "Increase thickness to 6 mm.", "current_revision_id": revision["id"]},
        ).json()
        assert change["parsed_spec"]["hole_features"] == parsed["parsed_spec"]["hole_features"]
        second = client.post(
            f"/api/projects/{project['id']}/revisions",
            headers=auth,
            json={"spec": change["parsed_spec"], "parent_id": revision["id"], "confirmed": True},
        ).json()
        assert second["parent_id"] == revision["id"]
        assert (
            client.get(f"/api/revisions/{revision['id']}", headers=auth).json()["spec"][
                "parameters"
            ]["thickness_mm"]
            == 5
        )
        assert (
            len(client.get(f"/api/projects/{project['id']}", headers=auth).json()["revisions"]) == 2
        )
        assert (
            client.get("/api/revisions/not-a-uuid/downloads/step", headers=auth).status_code == 422
        )
        assert client.post("/api/parse", headers=auth, json={"text": "x" * 4001}).status_code == 422


def test_confirmation_and_invalid_geometry_are_enforced(tmp_path):
    with TestClient(create_app(tmp_path, "secret", probe=False)) as client:
        assert not client.get("/api/health").json()["ready"]
        login = client.post("/api/sessions", json={"secret": "secret"}).json()
        auth = {"Authorization": "Bearer " + login["token"]}
        project = client.post("/api/projects", headers=auth, json={"name": "Validation"}).json()
        spec = client.post("/api/parse", headers=auth, json={"text": PROMPT}).json()["parsed_spec"]
        path = f"/api/projects/{project['id']}/revisions"
        assert (
            client.post(path, headers=auth, json={"spec": spec, "confirmed": False}).status_code
            == 422
        )
        spec["hole_features"][0]["positions_mm"][0] = [70, 5]
        assert (
            client.post(path, headers=auth, json={"spec": spec, "confirmed": True}).status_code
            == 422
        )
        assert not client.get(f"/api/projects/{project['id']}", headers=auth).json()["revisions"]
