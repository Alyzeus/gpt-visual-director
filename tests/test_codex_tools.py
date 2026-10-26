import copy
import argparse
from io import BytesIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from PIL import Image, ImageChops
from fontTools.ttLib import TTFont, TTCollection


parser = argparse.ArgumentParser(description='Exercise project storage, technique retrieval and actual CJK layout rendering without network or model calls.')
parser.add_argument('--skill', type=Path, default=Path(__file__).resolve().parents[1] / 'codex-visual-director')
parser.add_argument('--cjk-font', type=Path, required=True, help='Existing CJK font; fonts are not downloaded or bundled')
parser.add_argument('--latin-font', type=Path, required=True, help='Existing Latin-only font for missing-glyph rejection')
parser.add_argument('--output', type=Path, default=Path(tempfile.gettempdir()))
parser.add_argument('--report', type=Path)
args = parser.parse_args()
SKILL = args.skill.resolve()
BASE = args.output.resolve()
BASE.mkdir(parents=True, exist_ok=True)
ROOT = Path(tempfile.mkdtemp(prefix='checks with spaces-', dir=BASE))
FONT = args.cjk_font.resolve()
CASES = []


def call(script, *args, ok=True):
    p = subprocess.run([sys.executable, str(SKILL / 'scripts' / script), *map(str, args)],
                       capture_output=True, text=True)
    assert p.returncode == (0 if ok else 2), (script, args, p.returncode, p.stdout, p.stderr)
    data = json.loads(p.stdout if ok else p.stderr)
    if not ok:
        assert data['status'] == 'error'
    return data


def check(name, fn):
    try:
        fn()
        CASES.append({'case': name, 'passed': True})
    except Exception as e:
        CASES.append({'case': name, 'passed': False, 'error': repr(e)})


def expect(condition, detail='assertion failed'):
    assert condition, detail


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')


project = ROOT / 'project'
project.mkdir()
(project / 'brief.md').write_text('BR001\nKeep the original identity and direction.', encoding='utf-8')
first = ROOT / 'first.png'
second = ROOT / 'second.png'
Image.new('RGB', (24, 24), '#123456').save(first)
Image.new('RGB', (24, 24), '#654321').save(second)

check('P01 init preserves existing brief', lambda: (
    call('project.py', 'init', project),
    expect((project / 'brief.md').read_text().startswith('BR001'))))
check('P02 repeated init refuses overwrite', lambda: call('project.py', 'init', project, ok=False))
check('P03 add copies actual bytes', lambda: (
    call('project.py', 'add', project, first, '--id', 'v001'),
    expect((project / 'versions/v001/artifact.png').read_bytes() == first.read_bytes())))
check('P04 duplicate version refuses overwrite', lambda: call('project.py', 'add', project, second, '--id', 'v001', ok=False))
check('P05 confirmed edit requires evidence', lambda: call('project.py', 'add', project, second, '--id', 'v002', '--parent', 'v001', '--edit-input', 'confirmed', ok=False))
check('P06 parent defaults to unverified', lambda: (
    call('project.py', 'add', project, second, '--id', 'v002', '--parent', 'v001'),
    expect(json.loads((project / 'TASK_STATE.json').read_text())['versions']['v002']['edit_input_status'] == 'unverified')))
check('P07 rollback restores original and retains latest', lambda: (
    call('project.py', 'select', project, 'v002', '--reason', 'storage fixture'),
    call('project.py', 'select', project, 'v001', '--reason', 'storage rollback fixture'),
    expect((project / 'selected/v001.png').read_bytes() == first.read_bytes()),
    expect(json.loads((project / 'TASK_STATE.json').read_text())['current_version'] == 'v002')))

def conflict():
    target = project / 'selected/v001.png'
    target.write_bytes(b'conflict')
    call('project.py', 'select', project, 'v001', '--reason', 'fixture', ok=False)
    expect(target.read_bytes() == b'conflict')
    target.write_bytes(first.read_bytes())
check('P08 selected conflict is preserved', conflict)

def missing():
    target = project / 'versions/v001/artifact.png'
    raw = target.read_bytes()
    target.unlink()
    call('project.py', 'select', project, 'v001', '--reason', 'fixture', ok=False)
    target.write_bytes(raw)
check('P09 missing original cannot be faked as rollback', missing)

ref = project / 'references/ref.png'
ref.parent.mkdir()
shutil.copyfile(first, ref)
check('P10 reference records origin and roles', lambda: (
    call('project.py', 'reference', project, '--id', 'ref01', '--source', 'references/ref.png', '--origin', 'generated', '--role', 'comparison', '--role', 'edit_input', '--inspection', 'viewed', '--evidence', 'fixture image opened'),
    expect(json.loads((project / 'TASK_STATE.json').read_text())['versions']['v002']['edit_input_status'] == 'unverified')))
check('P11 reference duplicate refuses overwrite', lambda: call('project.py', 'reference', project, '--id', 'ref01', '--source', 'references/ref.png', '--origin', 'external', '--role', 'identity', ok=False))
check('P12 viewed reference needs evidence', lambda: call('project.py', 'reference', project, '--id', 'ref02', '--source', 'references/ref.png', '--origin', 'external', '--role', 'style', '--inspection', 'viewed', ok=False))
check('P13 reference cannot escape project', lambda: call('project.py', 'reference', project, '--id', 'bad', '--source', '../first.png', '--origin', 'user', '--role', 'style', ok=False))
check('P14 match checkpoint requires registered version', lambda: call('project.py', 'checkpoint', project, '--name', 'match', '--result', 'pass', '--basis', 'self_check', '--brief-revision', 'BR001', '--evidence', 'fixture', ok=False))

def checkpoints():
    before = json.loads((project / 'TASK_STATE.json').read_text())['stage']
    for revision, result in [('BR001', 'pass'), ('BR002', 'uncertain')]:
        call('project.py', 'checkpoint', project, '--name', 'match', '--result', result, '--basis', 'self_check',
             '--brief-revision', revision, '--version', 'v001', '--evidence', 'synthetic metadata fixture')
    state = json.loads((project / 'TASK_STATE.json').read_text())
    expect(len(state['checkpoints']) == 2)
    expect(state['stage'] == before)
    expect([v['brief_revision'] for v in state['checkpoints'].values()] == ['BR001', 'BR002'])
check('P15 checkpoints append with Brief scope and do not advance stage', checkpoints)

def moved():
    target = ROOT / 'relocated project'
    shutil.copytree(project, target)
    result = call('project.py', 'status', target)
    expect(result['storage_ok'])
check('P16 relocated state and references remain readable', moved)

def old_state():
    target = ROOT / 'old schema project'
    shutil.copytree(project, target)
    state = json.loads((target / 'TASK_STATE.json').read_text())
    state.pop('references')
    state.pop('checkpoints')
    write_json(target / 'TASK_STATE.json', state)
    expect(call('project.py', 'status', target)['storage_ok'])
    call('project.py', 'checkpoint', target, '--name', 'preflight', '--result', 'uncertain', '--basis', 'self_check', '--brief-revision', 'BR001', '--evidence', 'fixture')
    expect(len(json.loads((target / 'TASK_STATE.json').read_text())['checkpoints']) == 1)
check('P17 old schema remains compatible', old_state)

def bad_state(value):
    target = ROOT / ('bad state ' + str(len(CASES)))
    target.mkdir()
    (target / 'TASK_STATE.json').write_text(value, encoding='utf-8')
    call('project.py', 'status', target, ok=False)
check('P18 corrupt state has structured error', lambda: bad_state('{bad'))
check('P19 nonobject state has structured error', lambda: bad_state('[]'))
escaped = {'schema_version': 1, 'versions': {'v001': {'artifact': '../first.png'}}}
check('P20 state artifact escape is rejected', lambda: bad_state(json.dumps(escaped)))

check('T01 Chinese retrieval returns full conditions and counterexamples', lambda: (
    expect(call('techniques.py', 'search', '--query', '人物与环境 门把叙事', '--task-type', 'character')['results'][0]['card']['id'] == 'VD-T001'),
    expect(bool(call('techniques.py', 'search', '--query', '人物与环境')['results'][0]['card']['avoid_when']))))
check('T02 task filter excludes unrelated narrative cards', lambda: expect(all(
    'type' in v['card']['task_types'] or 'general' in v['card']['task_types'] for v in
    call('techniques.py', 'search', '--query', '字高 排版', '--task-type', 'type')['results'])))
check('T03 unrelated query returns no forced match', lambda: expect(call('techniques.py', 'search', '--query', 'zxqvnomatch849')['results'] == []))
cards = json.loads((SKILL / 'references/techniques.json').read_text())
card = copy.deepcopy(cards['cards'][0])
card['id'] = 'CHECK-T001'
card_file = ROOT / 'card.json'
write_json(card_file, card)
library = ROOT / 'project cards.json'
check('T04 add creates explicit project library', lambda: (
    call('techniques.py', 'add', '--library', library, '--card', card_file),
    expect(json.loads(library.read_text())['cards'][0]['status'] == 'proposed')))
check('T05 duplicate card refuses overwrite', lambda: call('techniques.py', 'add', '--library', library, '--card', card_file, ok=False))
check('T06 bundled seed library is not modified by add', lambda: call('techniques.py', 'add', '--library', SKILL / 'references/techniques.json', '--card', card_file, ok=False))

def missing_evidence():
    bad = copy.deepcopy(card)
    bad['id'], bad['status'] = 'CHECK-T002', 'supported'
    path = ROOT / 'bad card.json'
    write_json(path, bad)
    call('techniques.py', 'add', '--library', library, '--card', path, ok=False)
check('T07 evidence status cannot be added without any evidence record', missing_evidence)

def conflicting_cards():
    altered = copy.deepcopy(cards)
    altered['cards'][0]['mechanism'] = 'Different content, same ID'
    file = ROOT / 'conflicting cards.json'
    write_json(file, altered)
    call('techniques.py', 'search', '--query', '人物', '--library', SKILL / 'references/techniques.json', '--library', file, ok=False)
check('T08 conflicting ID across libraries refuses silent replacement', conflicting_cards)

layout = json.loads((SKILL / 'assets/layout-example.json').read_text())
def layout_run(name, config, ok=True, font=FONT):
    path = ROOT / (name + '.json')
    write_json(path, config)
    result = call('render_layout.py', path, '--out', ROOT / name, '--font', font, ok=ok)
    if not ok:
        expect(not any(Path(str(ROOT / name) + x).exists() for x in ('.png', '.svg', '.report.json')))
    return result

def valid_render():
    layout_run('valid layout', layout)
    with Image.open(ROOT / 'valid layout.png') as image:
        image.load()
        expect(image.size == (1200, 1800))
        expect(ImageChops.difference(image, Image.new('RGB', image.size, image.getpixel((1199, 1799)))).getbbox() is not None)
    svg = ET.parse(ROOT / 'valid layout.svg').getroot()
    nodes = svg.findall('{http://www.w3.org/2000/svg}text')
    expect('雨后的' in [n.text for n in nodes] and '回眸' in [n.text for n in nodes])
    import base64
    style = svg.find('{http://www.w3.org/2000/svg}style').text
    raw = style.split('base64,')[1].split(')')[0]
    with TTFont(BytesIO(base64.b64decode(raw))) as font:
        expect(all(ord(c) in font.getBestCmap() for c in '雨后的回眸'))
    report = json.loads((ROOT / 'valid layout.report.json').read_text())
    expect(report['blocks'][0]['lines'][0]['ink_bbox'][3] - report['blocks'][0]['lines'][0]['ink_bbox'][1] >= 70)
check('L01 real CJK PNG and SVG text/font subset are produced', valid_render)

def modified(name, mutate):
    config = copy.deepcopy(layout)
    mutate(config)
    layout_run(name, config, ok=False)

check('L02 missing glyphs reject rather than draw boxes', lambda: layout_run('missing glyphs', layout, ok=False, font=args.latin_font.resolve()))
check('L03 nonexistent font reports actual missing file', lambda: layout_run('missing font', layout, ok=False, font=ROOT / 'absent.ttf'))
broken_font = ROOT / 'corrupt.ttf'
broken_font.write_bytes(b'not a font')
check('L04 corrupt font returns structured error', lambda: layout_run('corrupt font', layout, ok=False, font=broken_font))
check('L05 unsupported layout fields are rejected', lambda: modified('unknown field', lambda c: c['blocks'][0].update(anchor='top_left')))
check('L06 horizontal overflow rejects output', lambda: modified('horizontal overflow', lambda c: c['blocks'][0].update(rect=[96, 180, 40, 320])))
check('L07 vertical overflow rejects output', lambda: modified('vertical overflow', lambda c: c['blocks'][0].update(rect=[96, 180, 500, 50])))
check('L08 actual ink must respect safe margin', lambda: modified('safe margin', lambda c: c['blocks'][0].update(rect=[0, 180, 500, 320])))
check('L09 actual ink must avoid protected regions', lambda: modified('protected region', lambda c: c.update(protected_regions=[{'id': 'face', 'rect': [96, 180, 500, 320]}])))

def overlap(c):
    extra = copy.deepcopy(c['blocks'][0])
    extra['id'] = 'overlap'
    c['blocks'].append(extra)
check('L10 visible text blocks cannot overlap', lambda: modified('block overlap', overlap))
check('L11 actual lines cannot overlap', lambda: modified('line overlap', lambda c: c['blocks'][0].update(line_height=5)))
check('L12 actual ink height is checked', lambda: modified('ink height', lambda c: c['blocks'][0].update(min_ink_height=150)))

def no_overwrite():
    old = (ROOT / 'valid layout.png').read_bytes()
    call('render_layout.py', ROOT / 'valid layout.json', '--out', ROOT / 'valid layout', '--font', FONT, ok=False)
    expect((ROOT / 'valid layout.png').read_bytes() == old)
check('L13 existing output is preserved', no_overwrite)

def edit_title():
    config = copy.deepcopy(layout)
    config['blocks'][0]['text'] = '晨光中\n相遇'
    layout_run('changed title', config)
    expect((ROOT / 'changed title.png').read_bytes() != (ROOT / 'valid layout.png').read_bytes())
    expect(json.loads((ROOT / 'changed title.report.json').read_text())['blocks'][0]['text'] == '晨光中\n相遇')
check('L14 changing title actually changes rendered output', edit_title)

check('L15 background mismatch needs explicit fit', lambda: modified('background mismatch', lambda c: c.update(background={'image': str(first), 'fit': 'exact'})))
check('L16 explicit background contain is implemented', lambda: layout_run('background contain', dict(layout, background={'image': str(first), 'fit': 'contain'})))
check('L17 missing optional thresholds are not claimed as checked', lambda: (
    layout_run('no optional checks', dict(layout, protected_regions=[], blocks=[dict(layout['blocks'][2])])),
    expect(json.loads((ROOT / 'no optional checks.report.json').read_text())['checks']['minimum_ink_height'] == 'not_applicable')))

def collection_font():
    ttc = ROOT / 'collection.ttc'
    collection = TTCollection()
    collection.fonts = [TTFont(args.latin_font.resolve())]
    collection.save(ttc)
    collection.close()
    simple = copy.deepcopy(layout)
    simple['blocks'] = [dict(simple['blocks'][2], text='FONT COLLECTION / 01', font_index=0)]
    layout_run('collection font', simple, font=ttc)
check('L18 actual TTC font member can render and embed', collection_font)

def automatic_wrap():
    config = copy.deepcopy(layout)
    config['blocks'][0].update(text='雨后的回眸', rect=[96, 180, 250, 440])
    layout_run('automatic wrap', config)
    lines = json.loads((ROOT / 'automatic wrap.report.json').read_text())['blocks'][0]['lines']
    expect(len(lines) > 1)
    expect(''.join(v['text'] for v in lines) == '雨后的回眸')
check('L19 automatic CJK wrapping preserves actual content', automatic_wrap)

def alignments():
    positions = []
    for align in ('left', 'center', 'right'):
        config = copy.deepcopy(layout)
        config['blocks'] = [dict(config['blocks'][2], align=align)]
        name = 'align ' + align
        layout_run(name, config)
        report = json.loads((ROOT / (name + '.report.json')).read_text())
        positions.append(report['blocks'][0]['ink_bbox'][0])
    expect(positions[0] < positions[1] < positions[2])
check('L20 left center and right alignment change rendered ink positions', alignments)

report = {'root': str(ROOT), 'passed': sum(x['passed'] for x in CASES), 'total': len(CASES), 'cases': CASES}
(args.report or ROOT / 'checks.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit(0 if report['passed'] == report['total'] else 1)
