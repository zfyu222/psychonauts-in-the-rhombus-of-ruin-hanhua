"""Build and round-trip both distance fonts against the three formal CSVs."""
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parents[1]
PROBE = WORKSPACE / 'Tools/unreal_assets/bin/Debug/net10.0/UnrealAssetProbe.exe'

def run(*args):
    subprocess.run([str(a) for a in args], check=True, capture_output=True)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

if __name__ == '__main__':
    out = ROOT / 'Analysis/formal-fonts-v1'
    out.mkdir()
    texts = [ROOT / (ROOT.name + '_text_translated.csv'),
             ROOT / 'TranslateFiles/ui-text' / (ROOT.name + '_ui_text_translated.csv'),
             ROOT / (ROOT.name + '_images_text_translated.csv')]
    jobs = [('SubtitleFontDistanceField', ROOT / 'Analysis/uasset-probe-v1/SubtitleFontDistanceField.json'),
            ('PsychonautsDistanceField', ROOT / 'Analysis/uasset-probe-fonts-v1/PsychonautsDistanceField/PsychonautsDistanceField.json')]
    reports = []
    for name, original in jobs:
        build = out / name
        run(sys.executable, ROOT / 'Analysis/prepare_distance_font.py', '--text-files', *texts,
            '--asset-json', original, '--out', build)
        run(PROBE, build / (name + '.json'), build / 'pass1')
        run(PROBE, build / 'pass1' / (name + '.uasset'), build / 'layout')
        run(sys.executable, ROOT / 'Analysis/prepare_distance_font.py',
            '--fix-offsets', build / 'layout' / (name + '.json'), '--out', build / 'fixed.json')
        run(PROBE, build / 'fixed.json', build / 'fixed')
        run(PROBE, build / 'fixed/fixed.uasset', build / 'verify')
        first, second = build / 'fixed/fixed.uasset', build / 'verify/fixed.uasset'
        if first.read_bytes() != second.read_bytes():
            raise ValueError('Font binary round-trip failed: ' + name)
        parsed = json.loads((build / 'verify/fixed.json').read_text(encoding='utf-8-sig'))
        import base64, struct
        remap = base64.b64decode(parsed['Exports'][0]['Extras'])
        count = struct.unpack_from('<i', remap)[0]
        codes = {struct.unpack_from('<HH', remap, 4 + i*4)[0] for i in range(count)}
        required = {ord(c) for text in texts for row in csv.reader(text.open(encoding='utf-8-sig', newline='')) for c in row[0] if not c.isspace()}
        missing = required - codes
        if missing:
            raise ValueError('Formal text glyphs missing: ' + repr(missing))
        reports.append(dict(font=name, path=str(first), sha256=sha(first),
                            mapped_characters=count, missing_formal_glyphs=0,
                            binary_roundtrip=True, visual_check='pending'))
    report = dict(source_csv_hashes={str(p): sha(p) for p in texts}, fonts=reports,
                  installed=False, in_game_check='pending')
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=True))
