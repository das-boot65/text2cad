"""Summarize existing measurements and preserve the first failed evaluation."""
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

root=Path(__file__).resolve().parents[1]
data=json.loads((root/'benchmark/results.json').read_text(encoding='utf-8'))
initial=json.loads((root/'benchmark/initial_results.json').read_text(encoding='utf-8'))
geometry=data['geometry']
def split_count(run,split):
    row=run['by_split'][split]
    return f"{row['passed']}/{row['total']}"
def outcome_count(run):
    return f"{sum(row['passed'] for row in run['raw_cases'])}/{len(run['raw_cases'])}"
def timing(value):
    return f'{value:.2f}' if value is not None else 'not available'
invalid_cases=[row for row in data['raw_cases'] if row['expected_status']=='invalid']
invalid_rejected=sum(row['actual_status']=='invalid' for row in invalid_cases)
fig,axis=plt.subplots(figsize=(10,4),layout='constrained')
labels=[f"{row['family']} {index+1}" for index,row in enumerate(geometry)]
axis.barh(labels,[row['generation_ms'] if row['valid'] else float('nan') for row in geometry],color='#6d9275')
for index,row in enumerate(geometry):
    if not row['valid']:
        axis.text(0,index,'FAILED',color='#a74738',va='center')
axis.set_xlabel('Warm generation + export/readback (ms); worker startup excluded')
axis.set_title(f'Text2CAD — {len(geometry)} actual local geometry checks')
axis.grid(axis='x',alpha=.2);axis.set_axisbelow(True)
fig.savefig(root/'benchmark/generation.png',dpi=160)
lines=['# Measured internal evaluation','',f"Environment: {json.dumps(data['environment'])}",'',
       data['methodology'],'','## Parser outcomes','',
       '| Run | Development | Original held-out labels | Total normalized outcomes |',
       '| --- | --- | --- | --- |',
       f"| First evaluation | {split_count(initial,'development')} | {split_count(initial,'held_out')} | {outcome_count(initial)} |",
       f"| Corrected regression rerun | {split_count(data,'development')} | {split_count(data,'held_out')} | {outcome_count(data)} |",'',
       'The first held-out miss classified a missing taper length as invalid rather than',
       'asking a clarification. That missing critical parameter now produces a question.',
       '**The rerun reuses observed examples and is not a new blind hold-out result.**',
       'No external dataset or general-language accuracy is claimed. Initial results are',
       'preserved in benchmark/initial_results.json; full per-case comparisons are in',
       'benchmark/results.json and benchmark/cases.csv. Optional metadata/provenance text',
       'is excluded from normalized-spec comparison and not silently counted correct.','',
       f"Annotated slot precision / recall / F1: {data['slot_precision']:.3f} / {data['slot_recall']:.3f} / {data['slot_f1']:.3f}.",
       f"Clarification precision: {timing(data['clarification_precision'])}. Invalid-request rejection: {invalid_rejected}/{len(invalid_cases)} authored invalid cases.",'',
       '## Geometry','',
       'Initial geometry evaluation: 7/8 passed. The screw-post enclosure exposed',
       'touching base/lid meshes in the exploded preview. Posts now overlap wall',
       'material and the lowest lid surface has a real 3 mm display separation.',
       f"The watertightness assertion was retained. Current result: {sum(row['valid'] for row in geometry)}/{len(geometry)} samples passed",
       'OCC validity, solid count, positive volume, bbox, through-hole removal,',
       'STEP readback and watertight/nonempty STL readback.','',
       f"Warm generation median: {timing(data['generation_median_ms'])} ms; sampled p95: {timing(data['generation_p95_ms'])} ms.",
       'Eight samples do not support a robust performance claim. Timing includes actual',
       'engine/export/readback, excludes interpreter/import/queue/browser time, and was',
       'affected by concurrent memory pressure on a 7.8 GiB Windows host. Real subprocess',
       'jobs take materially longer; see worker_jobs.json when captured.','',
       '![Measured warm generation](../benchmark/generation.png)','',
       '## Reproduce','',
       'Run `.venv/Scripts/python scripts/evaluate.py` then',
       '`.venv/Scripts/python scripts/report.py` from the repository root.',
       'The first result is a fixed historical artifact; regeneration does not overwrite it.',
       'Every generated part still requires engineering review for loads, fit, material',
       'and manufacturing suitability. No certification is implied.']
(root/'docs').mkdir(exist_ok=True)
(root/'docs/RESULTS.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print('Wrote docs/RESULTS.md and benchmark/generation.png')
