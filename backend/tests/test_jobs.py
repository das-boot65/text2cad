import time

from app.jobs import Jobs
from app.storage import Store


def wait(store, job):
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        result = store.record(job["id"])
        if result["state"] in ("cancelled", "failed", "completed"):
            return result
        time.sleep(0.02)
    raise AssertionError("Job did not terminate")


def test_worker_timeout_and_cancellation(tmp_path):
    store = Store(tmp_path)
    jobs = Jobs(store, tmp_path / "artifacts", timeout=0.001)
    revision = {
        "id": "test-revision",
        "spec": {
            "part_family": "plate",
            "parameters": {"length_mm": 60, "width_mm": 25, "thickness_mm": 5},
        },
    }
    try:
        first = jobs.submit(revision)
        result = wait(store, first)
        assert result["state"] == "failed" and result["error_code"] == "GENERATION_TIMEOUT"
        second = jobs.submit(revision)
        jobs.cancel(second["id"])
        assert wait(store, second)["state"] == "cancelled"
    finally:
        jobs.close()
        store.close()
