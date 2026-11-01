"""Versioned SQLite persistence with atomic revision-head compare-and-swap."""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    Column,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    func,
    select,
    update,
)

metadata = MetaData()
projects = Table(
    "projects",
    metadata,
    Column("id", String, primary_key=True),
    Column("name", String),
    Column("head_id", String),
    Column("created_at", String),
)
revisions = Table(
    "revisions",
    metadata,
    Column("id", String, primary_key=True),
    Column("project_id", String, index=True),
    Column("parent_id", String),
    Column("spec", Text),
    Column("diff", Text),
    Column("created_at", String),
)
records = Table(
    "records",
    metadata,
    Column("id", String, primary_key=True),
    Column("kind", String, index=True),
    Column("payload", Text),
)


def utc():
    return datetime.now(UTC).isoformat()


class Conflict(Exception):
    pass


class Store:
    def __init__(self, directory: Path):
        directory.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            f"sqlite:///{(directory / 'text2cad.sqlite3').as_posix()}",
            connect_args={"check_same_thread": False, "timeout": 10},
        )
        metadata.create_all(self.engine)
        with self.engine.begin() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL")
            conn.exec_driver_sql(
                "CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY)"
            )
            conn.exec_driver_sql("INSERT OR IGNORE INTO schema_versions VALUES (1)")
            # A previous process cannot still own a worker after a normal restart.
            for row in conn.execute(select(records).where(records.c.kind == "job")).all():
                job = json.loads(row.payload)
                if job["state"] in ("queued", "running"):
                    job.update(state="failed", error_code="SERVICE_RESTARTED", completed_at=utc())
                    conn.execute(
                        update(records)
                        .where(records.c.id == row.id)
                        .values(payload=json.dumps(job))
                    )

    def ping(self):
        with self.engine.connect() as conn:
            return conn.exec_driver_sql("SELECT 1").scalar() == 1

    def project(self, project_id: str):
        with self.engine.connect() as conn:
            row = (
                conn.execute(select(projects).where(projects.c.id == project_id)).mappings().first()
            )
            return dict(row) if row else None

    def projects(self):
        with self.engine.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    select(projects).order_by(projects.c.created_at.desc()).limit(100)
                ).mappings()
            ]

    def create_project(self, name: str):
        project = {"id": str(uuid4()), "name": name, "head_id": None, "created_at": utc()}
        with self.engine.begin() as conn:
            conn.execute(projects.insert().values(**project))
        return project

    def revision(self, revision_id: str):
        with self.engine.connect() as conn:
            row = (
                conn.execute(select(revisions).where(revisions.c.id == revision_id))
                .mappings()
                .first()
            )
            if not row:
                return None
            return {**dict(row), "spec": json.loads(row["spec"]), "diff": json.loads(row["diff"])}

    def history(self, project_id: str):
        with self.engine.connect() as conn:
            ids = (
                conn.execute(
                    select(revisions.c.id)
                    .where(revisions.c.project_id == project_id)
                    .order_by(revisions.c.created_at.desc())
                    .limit(100)
                )
                .scalars()
                .all()
            )
        return [self.revision(revision_id) for revision_id in ids]

    def commit(self, project_id: str, parent_id: str | None, spec: dict, diff: list):
        revision_id = str(uuid4())
        row = {
            "id": revision_id,
            "project_id": project_id,
            "parent_id": parent_id,
            "spec": json.dumps(spec),
            "diff": json.dumps(diff),
            "created_at": utc(),
        }
        with self.engine.begin() as conn:
            head_check = (
                projects.c.head_id == parent_id if parent_id else projects.c.head_id.is_(None)
            )
            result = conn.execute(
                update(projects)
                .where(projects.c.id == project_id, head_check)
                .values(head_id=revision_id)
            )
            if result.rowcount != 1:
                raise Conflict("Revision head changed; reload the project before committing.")
            conn.execute(revisions.insert().values(**row))
        return self.revision(revision_id)

    def save(self, record_id: str, kind: str, payload: dict):
        with self.engine.begin() as conn:
            conn.execute(delete(records).where(records.c.id == record_id))
            conn.execute(
                records.insert().values(id=record_id, kind=kind, payload=json.dumps(payload))
            )

    def record(self, record_id: str):
        with self.engine.connect() as conn:
            row = conn.execute(select(records.c.payload).where(records.c.id == record_id)).scalar()
            return json.loads(row) if row else None

    def list_records(self, kind: str):
        with self.engine.connect() as conn:
            return [
                json.loads(row)
                for row in conn.execute(
                    select(records.c.payload)
                    .where(records.c.kind == kind)
                    .order_by(func.json_extract(records.c.payload, "$.created_at").desc())
                    .limit(1000)
                ).scalars()
            ]

    def close(self):
        self.engine.dispose()

    def jobs_for_revision(self, revision_id: str):
        with self.engine.connect() as conn:
            query = (
                select(records.c.payload)
                .where(
                    records.c.kind == "job",
                    func.json_extract(records.c.payload, "$.revision_id") == revision_id,
                )
                .order_by(func.json_extract(records.c.payload, "$.created_at").desc())
                .limit(100)
            )
            return [json.loads(row) for row in conn.execute(query).scalars()]
