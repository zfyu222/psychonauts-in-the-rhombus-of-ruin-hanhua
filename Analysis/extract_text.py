"""Extract occurrence-bound dialogue JSON and legacy UE4 locres, read-only."""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1] / 'Tools/localization'))
from workflow_resource_occurrences import export_occurrences

BASE = ROOT / 'Analysis/extracted'
GAME = BASE / 'PsychonautsInTheRhombusOfRuin'
rows, context, excluded = [], {}, []

def add(text, resource, **metadata):
    if not text.strip():
        excluded.append({'resource': resource, 'reason': 'empty'})
        return
    rows.append({'source': text, 'resource': resource})
    context[str(len(rows))] = dict(resource=resource, **metadata)

p = GAME / 'Content/Dialog/Linecodes/MainGame_enUS.json'
dialog = json.loads(p.read_text(encoding='utf-8-sig'))['LineCodeData']
for key, item in dialog.items():
    resource = p.relative_to(BASE).as_posix() + '#LineCodeData/' + key + '/Text'
    if key == 'CMAP001TEXT':
        excluded.append({'resource': resource, 'reason': 'font character-map test, not dialogue'})
        continue
    add(item['Text'], resource, group='dialogue', speaker=item.get('Character', ''),
        text_type='UI' if item.get('Character') == 'Text' else 'dialogue', note='Linecode: ' + key)

dialogue_count = len(rows)
p = GAME / 'Content/Localization/Game/en/Game.locres'
data = p.read_bytes()
pos = 0
def integer():
    global pos
    value = struct.unpack_from('<i', data, pos)[0]
    pos += 4
    return value

def string():
    global pos
    size = integer()
    assert abs(size) < 1000000
    if not size:
        return ''
    length = abs(size) * (2 if size < 0 else 1)
    raw = data[pos:pos+length]
    assert len(raw) == length
    pos += length
    value = raw.decode('utf-16-le' if size < 0 else 'utf-8')
    assert value.endswith('\0')
    return value[:-1]

for _ in range(integer()):
    namespace = string()
    for _ in range(integer()):
        key = string()
        source_crc = integer() & 0xffffffff
        value = string()
        add(value, p.relative_to(BASE).as_posix() + '#' + namespace + '/' + key,
            group='menu', text_type='UI', note=f'namespace={namespace}; key={key}; crc={source_crc:08x}')
assert pos == len(data), (pos, len(data))
name = ROOT.name + '_text'
count = export_occurrences(rows, ROOT / (name + '.csv'), ROOT / (name + '.mapping.json'))
(ROOT / (name + '.context.json')).write_text(json.dumps(context, ensure_ascii=False, indent=2), encoding='utf-8')
report = dict(records=count, dialogue_records=dialogue_count, locres_records=count-dialogue_count,
              exclusions=excluded, inputs={str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in [GAME/'Content/Dialog/Linecodes/MainGame_enUS.json', GAME/'Content/Localization/Game/en/Game.locres']})
(ROOT / 'Analysis/extraction-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=True))
