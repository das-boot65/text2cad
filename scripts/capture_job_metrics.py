"""Capture nonsecret measurements from real local jobs (run after the browser demo)."""
import json
import sqlite3
from pathlib import Path

root=Path(__file__).resolve().parents[1]
with sqlite3.connect(root/'data/text2cad.sqlite3') as connection:
    jobs=[json.loads(row[0]) for row in connection.execute('SELECT payload FROM records WHERE kind=?',('job',))]
keys=('id','revision_id','state','elapsed_ms','windows_job_limits','worker_exit_code','error_code','created_at','completed_at')
(root/'benchmark/worker_jobs.json').write_text(json.dumps([{k:job.get(k) for k in keys} for job in jobs],indent=2),encoding='utf-8')
print(f'Captured {len(jobs)} real worker jobs without credentials or local paths')
