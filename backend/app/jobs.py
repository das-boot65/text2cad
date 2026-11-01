"""Single-worker, bounded and cancellable CAD jobs; output paths are server-owned."""

import hashlib
import json
import logging
import os
import queue
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

from .storage import Store, utc
from .windows_limits import contain


class Busy(Exception):
    pass


class Jobs:
    def __init__(self, store: Store, directory: Path, timeout: float = 60):
        self.store, self.directory, self.timeout = store, directory, timeout
        self.directory.mkdir(parents=True, exist_ok=True)
        self.pending: queue.Queue = queue.Queue(maxsize=8)
        self.lock = threading.RLock()
        self.stopping = threading.Event()
        self.cancelled: set[str] = set()
        self.process: subprocess.Popen | None = None
        self.ready = False
        self.probe_details: dict = {}
        self.worker = threading.Thread(target=self._loop, name="cad-supervisor", daemon=True)
        self.worker.start()

    def probe(self):
        try:
            result = subprocess.run(
                [sys.executable, "-m", "app.worker", "--probe"],
                cwd=Path(__file__).parents[1],
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
                stdin=subprocess.DEVNULL,
            )
            if result.returncode == 0:
                self.probe_details = json.loads(result.stdout)
                self.ready = bool(self.probe_details.get("valid"))
            else:
                self.probe_details = {"valid": False, "error_code": "CAD_DEPENDENCIES_UNAVAILABLE"}
        except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError):
            self.ready = False
            self.probe_details = {"valid": False, "error_code": "CAD_PROBE_FAILED"}
        return self.ready

    def submit(self, revision: dict):
        with self.lock:
            active = [
                j for j in self.store.list_records("job") if j["state"] in ("queued", "running")
            ]
            if len(active) >= 8:
                raise Busy("At most eight CAD jobs can be active.")
            if any(j["revision_id"] == revision["id"] for j in active):
                raise Busy("A generation job for this revision is already active.")
            # Disk retention: reject new work at 2 GiB; no automatic user-data deletion.
            size = sum(p.stat().st_size for p in self.directory.rglob("*") if p.is_file())
            if size > 2 * 1024**3:
                raise Busy(
                    "Artifact storage limit reached; archive old output offline before generating."
                )
            job = {
                "id": str(uuid4()),
                "revision_id": revision["id"],
                "state": "queued",
                "created_at": utc(),
                "error_code": None,
                "artifacts": [],
            }
            self.store.save(job["id"], "job", job)
            try:
                self.pending.put_nowait((job, revision["spec"]))
            except queue.Full:
                job.update(state="failed", error_code="QUEUE_FULL")
                self.store.save(job["id"], "job", job)
                raise Busy("CAD queue is full.") from None
            return job

    def cancel(self, job_id: str):
        with self.lock:
            job = self.store.record(job_id)
            if not job:
                return None
            if job["state"] in ("queued", "running"):
                self.cancelled.add(job_id)
            return job

    def _loop(self):
        while not self.stopping.is_set():
            try:
                job, spec = self.pending.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                self._run(job, spec)
            except Exception:
                logging.getLogger(__name__).exception(
                    "cad_job_supervisor_failed job_id=%s", job["id"]
                )
                job.update(state="failed", error_code="SUPERVISOR_FAILURE", completed_at=utc())
                self.store.save(job["id"], "job", job)
            finally:
                self.cancelled.discard(job["id"])
                self.pending.task_done()

    def _run(self, job: dict, spec: dict):
        if job["id"] in self.cancelled:
            job.update(state="cancelled", completed_at=utc())
            self.store.save(job["id"], "job", job)
            return
        output = self.directory / job["id"]
        output.mkdir(parents=True, exist_ok=True)
        source = output / "input.json"
        source.write_text(json.dumps(spec), encoding="utf-8")
        job.update(state="running", started_at=utc())
        self.store.save(job["id"], "job", job)
        environment = {**os.environ, "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
        with (output / "worker.log").open("wb") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "app.worker", str(source.resolve()), str(output.resolve())],
                cwd=Path(__file__).parents[1],
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                env=environment,
            )
            self.process = process
            release = contain(process)
            job["windows_job_limits"] = bool(release)
            start = time.monotonic()
            reason = None
            try:
                while process.poll() is None:
                    if job["id"] in self.cancelled or self.stopping.is_set():
                        reason = "CANCELLED"
                    elif time.monotonic() - start > self.timeout:
                        reason = "GENERATION_TIMEOUT"
                    if reason:
                        process.terminate()
                        try:
                            process.wait(timeout=3)
                        except subprocess.TimeoutExpired:
                            process.kill()
                        break
                    time.sleep(0.02)
                process.wait(timeout=5)
            finally:
                if release:
                    release()
                self.process = None
        job["elapsed_ms"] = (time.monotonic() - start) * 1000
        job["worker_exit_code"] = process.returncode
        if reason or process.returncode != 0:
            job.update(
                state="cancelled" if reason == "CANCELLED" else "failed",
                error_code=reason or "GEOMETRY_GENERATION_FAILED",
            )
        else:
            report = json.loads((output / "validation_report.json").read_text(encoding="utf-8"))
            job.update(state="completed", validation=report)
            job["artifacts"] = [
                {
                    "id": str(uuid4()),
                    "file_type": file.suffix[1:],
                    "filename": file.name,
                    "size_bytes": file.stat().st_size,
                    "sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
                }
                for file in (
                    output / "model.step",
                    output / "model.stl",
                    output / "spec.json",
                    output / "validation_report.json",
                )
            ]
        job["completed_at"] = utc()
        self.store.save(job["id"], "job", job)

    def completed(self, revision_id: str):
        candidates = [
            j
            for j in self.store.jobs_for_revision(revision_id)
            if j["revision_id"] == revision_id and j["state"] == "completed"
        ]
        return max(candidates, key=lambda j: j["created_at"]) if candidates else None

    def close(self):
        self.stopping.set()
        if self.process and self.process.poll() is None:
            self.process.terminate()
        self.worker.join(timeout=10)
