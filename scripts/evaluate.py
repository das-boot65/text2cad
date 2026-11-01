"""Reproduce parser/geometry metrics and retain every raw case outcome."""
import csv
import json
import platform
import statistics
import sys
import tempfile
import time
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'backend'))
from app.cad import generate  # noqa: E402
from app.parsing import REQUIRED, RuleParser  # noqa: E402
from app.schemas import spec_adapter  # noqa: E402

corpus=json.loads((root/'examples/prompts/corpus.json').read_text(encoding='utf-8'))
raw=[]
correct_slots=predicted_slots=expected_slots=0
by_split={}
clarifications_correct=clarifications_returned=0
for case in corpus['cases']:
    before=spec_adapter.validate_python(case['current_spec']) if 'current_spec' in case else None
    start=time.perf_counter()
    result=RuleParser().parse(case['text'],before)
    parse_ms=(time.perf_counter()-start)*1000
    normalized=None
    if result.get('parsed_spec'):
        normalized={key:result['parsed_spec'][key] for key in ('part_family','units','parameters','hole_features')}
        normalized=json.loads(json.dumps(normalized))
    passed=result['status']==case['expected_status']
    if case['expected_status']=='ready':
        passed=passed and normalized==case['expected_normalized']
        expected=case['expected_slots']
        actual=normalized['parameters'] if normalized else {}
        universe=set(REQUIRED[case['family']])|set(expected)
        expected_slots+=len(expected)
        predicted_slots+=sum(key in actual for key in universe)
        correct_slots+=sum(key in actual and actual[key]==value for key,value in expected.items())
    if result['status']=='needs_clarification':
        clarifications_returned+=1
        clarifications_correct+=case['expected_status']=='needs_clarification'
    split=by_split.setdefault(case['split'],{'total':0,'passed':0})
    split['total']+=1
    split['passed']+=int(passed)
    raw.append({'id':case['id'],'split':case['split'],'text':case['text'],'expected_status':case['expected_status'],
                'actual_status':result['status'],'expected_normalized':case.get('expected_normalized'),
                'actual_normalized':normalized,'questions':result.get('questions'), 'passed':passed,'parse_ms':parse_ms})
geometry=[]
fixtures=[
 ('plate',{'length_mm':60,'width_mm':25,'thickness_mm':5},[{'diameter_mm':4.5,'positions_mm':[[10,5],[50,5],[10,20],[50,20]]}]),
 ('plate',{'length_mm':80,'width_mm':40,'thickness_mm':5,'corner_radius_mm':3},[]),
 ('bracket',{'length_mm':60,'width_mm':30,'height_mm':40,'thickness_mm':5},[]),
 ('bracket',{'length_mm':60,'width_mm':30,'height_mm':40,'thickness_mm':5,'corner_radius_mm':1},[{'face':'base','diameter_mm':4,'positions_mm':[[20,10],[45,20]]}]),
 ('enclosure',{'length_mm':80,'width_mm':50,'height_mm':30,'wall_mm':3,'lid_clearance_mm':.3},[]),
 ('enclosure',{'length_mm':100,'width_mm':80,'height_mm':30,'wall_mm':3,'lid_clearance_mm':.3,'screw_hole_diameter_mm':3},[]),
 ('finger',{'length_mm':80,'width_mm':20,'thickness_mm':6},[]),
 ('finger',{'length_mm':80,'width_mm':20,'thickness_mm':6,'tip':'tapered','taper_length_mm':20,'pad_depth_mm':1},[]),
]
with tempfile.TemporaryDirectory(prefix='text2cad-evaluation-') as temp:
    for index,(family,parameters,holes) in enumerate(fixtures):
        spec={'part_family':family,'parameters':parameters,'hole_features':holes}
        try:
            report=generate(spec,Path(temp)/str(index))
            geometry.append({'family':family,'spec':spec,**report})
        except (ValueError,RuntimeError) as exc:
            geometry.append({'family':family,'spec':spec,'valid':False,'error':str(exc),'generation_ms':None,'volume_mm3':None})
precision=correct_slots/predicted_slots if predicted_slots else 0
recall=correct_slots/expected_slots if expected_slots else 0
times=sorted(g['generation_ms'] for g in geometry if g['valid'])
output={'case_count':len(raw),'fully_correct_rate':sum(r['passed'] for r in raw)/len(raw),
        'slot_precision':precision,'slot_recall':recall,'slot_f1':2*precision*recall/(precision+recall) if precision+recall else 0,
        'clarification_precision':clarifications_correct/clarifications_returned if clarifications_returned else None,
        'by_split':by_split,'geometry_success_rate':sum(g['valid'] for g in geometry)/len(geometry),
        'generation_median_ms':statistics.median(times) if times else None,'generation_p95_ms':times[round((len(times)-1)*.95)] if times else None,
        'invalid_request_rejection_rate':sum(r['actual_status']=='invalid' for r in raw if r['expected_status']=='invalid')/sum(r['expected_status']=='invalid' for r in raw),
        'methodology':corpus['methodology']+' Full normalized outcome means status plus family, units, every canonical parameter and hole feature; source/provenance text is excluded. Slot metrics measure annotated required normalized slots and explicit revision slots; optional defaults are excluded. Geometry timing is warm in-process generation including export/readback, excluding worker startup. Eight geometry samples are a smoke evaluation, not a statistical performance study.',
        'environment':{'python':platform.python_version(),'platform':platform.platform(),'processor':platform.processor()},
        'raw_cases':raw,'geometry':geometry}
directory=root/'benchmark'
directory.mkdir(exist_ok=True)
(directory/'results.json').write_text(json.dumps(output,indent=2),encoding='utf-8')
with (directory/'cases.csv').open('w',encoding='utf-8',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=['id','split','expected_status','actual_status','passed','parse_ms'])
    writer.writeheader()
    writer.writerows([{key:row[key] for key in writer.fieldnames} for row in raw])
print(json.dumps({key:value for key,value in output.items() if key not in ('raw_cases','geometry')},indent=2))
if not all(row['passed'] for row in raw) or not all(row['valid'] for row in geometry):
    raise SystemExit(1)
