"""Authenticated local design API, bounded generation and safe artifact access."""

import asyncio
import io
import json
import os
import secrets
import threading
import time
import zipfile
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from .jobs import Busy, Jobs
from .limits import BodyLimit
from .parsing import DEFAULTS, REQUIRED, RuleParser, spec_diff
from .schemas import Login, ParseInput, ProjectInput, RevisionInput, Spec, spec_adapter
from .storage import Conflict, Store
from .validation import validate_spec


def create_app(data_dir: Path | None = None, secret: str | None = None, probe: bool = True):
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        directory = (data_dir or Path(os.getenv("TEXT2CAD_DATA", "data"))).resolve()
        app.state.store = Store(directory)
        app.state.jobs = Jobs(app.state.store, directory / "artifacts")
        app.state.secret = secret or os.getenv("TEXT2CAD_SECRET", "")
        app.state.sessions = {}
        app.state.session_lock = threading.Lock()
        app.state.parser = RuleParser()
        if probe:
            await asyncio.to_thread(app.state.jobs.probe)
        yield
        app.state.jobs.close()
        app.state.store.close()

    app = FastAPI(
        title="Text2CAD — constrained parametric design", version="1.0.0", lifespan=lifespan
    )
    app.add_middleware(BodyLimit, limit=65536)
    origins = os.getenv(
        "TEXT2CAD_ORIGINS", "http://127.0.0.1:5174,http://localhost:5174,http://127.0.0.1:8001"
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def limits(request: Request, call_next):
        correlation = str(uuid4())
        content_length = request.headers.get("content-length", "0")
        if not content_length.isdigit() or int(content_length) > 65536:
            return JSONResponse({"error": "BODY_TOO_LARGE", "correlation_id": correlation}, 413)
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(Conflict)
    async def conflict(request: Request, exc: Conflict):
        return JSONResponse({"error": "REVISION_CONFLICT", "message": str(exc)}, 409)

    @app.exception_handler(Busy)
    async def busy(request: Request, exc: Busy):
        return JSONResponse({"error": "RESOURCE_LIMIT", "message": str(exc)}, 429)

    def authenticated(request: Request, authorization: str = Header(default="")):
        token = authorization.removeprefix("Bearer ")
        session = request.app.state.sessions.get(token)
        if (
            not authorization.startswith("Bearer ")
            or not session
            or session["expires"] <= time.monotonic()
        ):
            raise HTTPException(401, "Session missing or expired; sign in with your local secret.")
        return session

    def revision_or_404(request: Request, revision_id: str):
        revision = request.app.state.store.revision(revision_id)
        if revision is None:
            raise HTTPException(404, "Revision not found")
        return revision

    @app.get("/api/health")
    def health(request: Request):
        jobs = request.app.state.jobs
        database = request.app.state.store.ping()
        return {
            "ready": jobs.ready and database and jobs.worker.is_alive(),
            "cad_worker": jobs.probe_details,
            "database": "ready" if database else "unavailable",
            "offline_parser": True,
            "authentication_configured": bool(request.app.state.secret),
        }

    @app.post("/api/sessions")
    def login(body: Login, request: Request):
        if not request.app.state.secret:
            raise HTTPException(503, "TEXT2CAD_SECRET is not configured; run setup and restart.")
        if not secrets.compare_digest(
            body.secret.encode("utf-8"), request.app.state.secret.encode("utf-8")
        ):
            raise HTTPException(401, "Invalid local secret")
        with request.app.state.session_lock:
            now = time.monotonic()
            sessions = request.app.state.sessions
            for key in list(sessions):
                if sessions[key]["expires"] <= now:
                    del sessions[key]
            if len(sessions) >= 100:
                raise HTTPException(429, "Session limit reached")
            token = secrets.token_urlsafe(32)
            result = {"session_id": str(uuid4()), "expires": now + 3600}
            sessions[token] = result
        return {"token": token, "session_id": result["session_id"], "expires_in": 3600}

    @app.get("/api/parts/families")
    def families():
        return {
            "families": [
                {
                    "id": family,
                    "required_parameters": required,
                    "optional_defaults": DEFAULTS[family],
                }
                for family, required in REQUIRED.items()
            ],
            "schema": spec_adapter.json_schema(),
            "units": "mm",
            "max_dimension_mm": 1000,
            "minimum_hole_edge_clearance_mm": 1,
        }

    @app.post("/api/parse")
    def parse(body: ParseInput, request: Request, current: dict = Depends(authenticated)):
        spec = None
        if body.current_revision_id:
            revision = revision_or_404(request, body.current_revision_id)
            spec = spec_adapter.validate_python(revision["spec"])
        return request.app.state.parser.parse(body.text, spec)

    @app.post("/api/validate")
    def validate(body: Spec, current: dict = Depends(authenticated)):
        return validate_spec(body)

    @app.get("/api/projects")
    def projects(request: Request, current: dict = Depends(authenticated)):
        return request.app.state.store.projects()

    @app.post("/api/projects")
    def create_project(
        body: ProjectInput, request: Request, current: dict = Depends(authenticated)
    ):
        return request.app.state.store.create_project(body.name)

    @app.get("/api/projects/{project_id}")
    def project(project_id: UUID, request: Request, current: dict = Depends(authenticated)):
        result = request.app.state.store.project(str(project_id))
        if result is None:
            raise HTTPException(404, "Project not found")
        return {**result, "revisions": request.app.state.store.history(str(project_id))}

    @app.post("/api/projects/{project_id}/revisions")
    def commit(
        project_id: UUID,
        body: RevisionInput,
        request: Request,
        current: dict = Depends(authenticated),
    ):
        if request.app.state.store.project(str(project_id)) is None:
            raise HTTPException(404, "Project not found")
        report = validate_spec(body.spec)
        if not report["valid"]:
            return JSONResponse({"error": "INVALID_GEOMETRY", "validation": report}, 422)
        parent = revision_or_404(request, body.parent_id) if body.parent_id else None
        if parent and parent["project_id"] != str(project_id):
            raise HTTPException(409, "Parent belongs to another project")
        normalized = body.spec.model_dump()
        diff = spec_diff(parent["spec"], normalized) if parent else []
        return request.app.state.store.commit(str(project_id), body.parent_id, normalized, diff)

    @app.get("/api/revisions/{revision_id}")
    def revision(revision_id: UUID, request: Request, current: dict = Depends(authenticated)):
        result = revision_or_404(request, str(revision_id))
        return {**result, "generation": request.app.state.jobs.completed(str(revision_id))}

    @app.post("/api/revisions/{revision_id}/generate")
    def generate(revision_id: UUID, request: Request, current: dict = Depends(authenticated)):
        if not request.app.state.jobs.ready:
            raise HTTPException(503, "CAD worker probe failed; check local dependencies.")
        return request.app.state.jobs.submit(revision_or_404(request, str(revision_id)))

    @app.get("/api/jobs/{job_id}")
    def job(job_id: UUID, request: Request, current: dict = Depends(authenticated)):
        result = request.app.state.store.record(str(job_id))
        if not result or "revision_id" not in result:
            raise HTTPException(404, "Job not found")
        return result

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel(job_id: UUID, request: Request, current: dict = Depends(authenticated)):
        result = request.app.state.jobs.cancel(str(job_id))
        if not result:
            raise HTTPException(404, "Job not found")
        return result

    def completed(request: Request, revision_id: str):
        revision_or_404(request, revision_id)
        result = request.app.state.jobs.completed(revision_id)
        if result is None:
            raise HTTPException(409, "Generate and validate this revision first")
        return result

    @app.get("/api/revisions/{revision_id}/validation")
    def validation(revision_id: UUID, request: Request, current: dict = Depends(authenticated)):
        return completed(request, str(revision_id))["validation"]

    @app.get("/api/revisions/{revision_id}/downloads/{format}")
    def download(
        revision_id: UUID, format: str, request: Request, current: dict = Depends(authenticated)
    ):
        filenames = {
            "step": "model.step",
            "stl": "model.stl",
            "json": "spec.json",
            "report": "validation_report.json",
        }
        if format not in filenames:
            raise HTTPException(404, "Format must be step, stl, json or report")
        result = completed(request, str(revision_id))
        return FileResponse(
            request.app.state.jobs.directory / result["id"] / filenames[format],
            filename=filenames[format],
        )

    @app.get("/api/revisions/{revision_id}/handoff")
    def handoff(revision_id: UUID, request: Request, current: dict = Depends(authenticated)):
        result = completed(request, str(revision_id))
        revision = revision_or_404(request, str(revision_id))
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
            for filename in ("model.step", "model.stl", "spec.json", "validation_report.json"):
                archive.write(request.app.state.jobs.directory / result["id"] / filename, filename)
            archive.writestr(
                "revision_history.json",
                json.dumps(request.app.state.store.history(revision["project_id"]), indent=2),
            )
            archive.writestr("generation_metadata.json", json.dumps(result, indent=2))
            archive.writestr(
                "README.txt",
                "Constrained parametric design. Not structurally or manufacturing certified. STEP is a neutral B-rep export; source JSON and approved template are canonical. Enclosure base/lid exported as separate solids with 3 mm display separation.",
            )
        return Response(
            stream.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": 'attachment; filename="engineering-handoff.zip"'},
        )

    @app.get("/api/evaluation")
    def evaluation(current: dict = Depends(authenticated)):
        file = Path(__file__).resolve().parents[2] / "benchmark" / "results.json"
        return (
            json.loads(file.read_text(encoding="utf-8"))
            if file.exists()
            else {
                "status": "not_run",
                "message": "Run scripts/evaluate.py locally to collect measured evidence.",
            }
        )

    dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.exists():
        app.mount("/", StaticFiles(directory=dist, html=True), name="studio")
    return app


app = create_app()
