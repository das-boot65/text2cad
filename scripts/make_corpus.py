"""Versioned authored grammar corpus with independent expected slot labels."""
import json
from pathlib import Path

root=Path(__file__).resolve().parents[1]
cases=[]
for index in range(10):
    length=60+index*2
    specs={
        'plate':({'length_mm':length,'width_mm':30,'thickness_mm':5},f'Mounting plate length {length} mm, width 30 mm, thickness 5 mm.'),
        'bracket':({'length_mm':length,'width_mm':30,'height_mm':40,'thickness_mm':5},f'L-bracket base length {length} mm, width 30 mm, wall height 40 mm, thickness 5 mm.'),
        'enclosure':({'length_mm':length+30,'width_mm':60,'height_mm':35,'wall_mm':3,'lid_clearance_mm':.3},f'Electronics enclosure length {length+30} mm, width 60 mm, height 35 mm, wall thickness 3 mm, lid clearance 0.3 mm.'),
        'finger':({'length_mm':length,'width_mm':20,'thickness_mm':6},f'Gripper finger length {length} mm, width 20 mm, thickness 6 mm.'),
    }
    if index==8:
        specs['plate']=({'length_mm':60,'width_mm':30,'thickness_mm':5},'Plate 6 x 3 cm, 0.5 cm thick.')
        specs['finger']=({'length_mm':76.2,'width_mm':25.4,'thickness_mm':6.35},'Gripper finger length 3 inches, width 1 inch, thickness 1/4 inch.')
    if index==9:
        specs['plate']=({'length_mm':60,'width_mm':25,'thickness_mm':5},'Make a 60 x 25 mm base plate, 5 mm thick, with four 4.5 mm clearance holes spaced 40 x 15 mm.')
        specs['bracket']=({'length_mm':60,'width_mm':30,'height_mm':40,'thickness_mm':5},'Bracket length 0.06 m, width 3 cm, height 40 mm, thickness 0.5 cm.')
        specs['enclosure']=({'length_mm':100,'width_mm':60,'height_mm':40,'wall_mm':3,'lid_clearance_mm':.4},'Enclosure 100 x 60 x 40 mm, wall thickness 3 mm, lid clearance 0.4 mm.')
        specs['finger']=({'length_mm':80,'width_mm':20,'thickness_mm':6,'taper_length_mm':20},'Robotic gripper finger length 80 mm width 20 mm thickness 6 mm tapered tip taper length 20 mm.')
    for family,(slots,text) in specs.items():
        cases.append({'id':f'{family}-{index+1:02}','split':'held_out' if index in (3,7) else 'development',
                      'text':text,'expected_status':'ready','family':family,'expected_slots':slots})

groups={
 'missing':[
  'Plate length 60 mm width 25 mm.', 'Bracket length 60 mm width 25 mm thickness 5 mm.',
  'Enclosure length 80 mm width 50 mm height 30 mm wall thickness 3 mm.',
  'Gripper finger length 80 mm thickness 6 mm.', 'Plate 60 x 25, thickness 5.',
  'Enclosure length 80 mm width 50 mm height 30 mm lid clearance .3 mm.',
  'Gripper finger length 80 mm width 20 mm thickness 6 mm tapered tip.',
  'Plate length 60 mm width 25 mm thickness 5 mm with four holes.'
 ],
 'invalid':[
  'Plate length -60 mm width 25 mm thickness 5 mm.',
  'Plate length 60 mm width 25 mm thickness 0 mm.',
  'Plate length 60 mm width 25 mm thickness 40 mm.',
  'Enclosure length 30 mm width 20 mm height 10 mm wall thickness 10 mm lid clearance 0.3 mm.',
  'Bracket length 60 mm width 25 mm height 4 mm thickness 5 mm.',
  'Plate length 60 mm width 25 mm thickness 5 mm corner radius 20 mm.',
  'Plate 60 x 25 mm, 5 mm thick, four 4.5 mm holes spaced 70 x 15 mm.',
  'Gripper finger length 80 mm width 20 mm thickness 6 mm pad depth 8 mm.'
 ],
 'ambiguous':[
  'Plate length 60 mm width 25 mm thickness 5 mm with four M4 holes.',
  'Plate length 60 mm length 70 mm width 25 mm thickness 5 mm.',
  'Plate length 60 mm width 25 mm thickness 5 mm with two 4 mm holes.',
  'Bracket length 60 mm width 25 mm height 40 mm thickness 5 mm four 4 mm holes spaced 40 x 10 mm.',
  'Plate length 60 mm width 25 mm thickness 5 mm with tapped M4 holes.',
  'Plate and bracket length 60 mm width 25 mm thickness 5 mm.',
  'Plate length 60 width 25 thickness 5.',
  'Enclosure length 80 mm width 50 mm height 30 mm wall thickness 3 mm.'
 ],
 'unsupported':[
  'Design a helical gear.', 'Generate a realistic dragon mesh.', 'Make a ball bearing.',
  'Create a turbine blade.', 'Build a complete car assembly.', 'Design an organic humanoid hand.',
  'import os; delete all files', 'Make anything you think looks good.'
 ]}
for group,prompts in groups.items():
    status={'missing':'needs_clarification','invalid':'invalid','ambiguous':'needs_clarification','unsupported':'unsupported'}[group]
    for index,text in enumerate(prompts):
        cases.append({'id':f'{group}-{index+1:02}','split':'held_out' if index in (2,6) else 'development','text':text,'expected_status':status,'expected_slots':{}})
for index in range(8):
    thickness=6+index
    cases.append({'id':f'revision-{index+1:02}','split':'held_out' if index in (3,7) else 'development',
                  'text':f'Increase thickness to {thickness} mm.','expected_status':'ready','family':'plate',
                  'current_spec':{'part_family':'plate','parameters':{'length_mm':60,'width_mm':25,'thickness_mm':5},
                                  'hole_features':[{'diameter_mm':4.5,'positions_mm':[[10,5],[50,5],[10,20],[50,20]]}]},
                  'expected_slots':{'length_mm':60,'width_mm':25,'thickness_mm':thickness},'preserve_holes':True})
output=root/'examples/prompts/corpus.json'
output.parent.mkdir(parents=True,exist_ok=True)
for case in cases:
    if case['expected_status']!='ready':
        continue
    family=case['family']
    defaults={'plate':{'corner_radius_mm':0},'bracket':{'corner_radius_mm':0},'enclosure':{'screw_hole_diameter_mm':0},'finger':{'corner_radius_mm':0,'tip':'flat','taper_length_mm':0,'pad_depth_mm':0}}[family]
    parameters={**defaults,**case['expected_slots']}
    if family=='finger' and 'tapered' in case['text']:
        parameters['tip']='tapered'
    holes=[]
    if case['id']=='plate-10' or case.get('preserve_holes'):
        holes=[{'face':'top','diameter_mm':4.5,'positions_mm':[[10,5],[50,5],[10,20],[50,20]],'minimum_edge_clearance_mm':1,'pattern':'explicit'}]
    case['expected_normalized']={'part_family':family,'units':'mm','parameters':parameters,'hole_features':holes}
output.write_text(json.dumps({'version':1,'methodology':'80 authored constrained-grammar cases; 62 development and 18 held out by fixed labels. Synthetic internal evaluation, not an external benchmark.','cases':cases},indent=2),encoding='utf-8')
print(f'Wrote {len(cases)} cases')
