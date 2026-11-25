"""Occurrence-bound UE4 JSON/legacy locres adapter; never writes to Game/."""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parents[1] / 'Tools/localization'))
from workflow_resource_occurrences import ResourceResolver, text_sha


class Locres:
    def __init__(self, data):
        self.data, self.pos = data, 0
        self.namespaces = []
        for _ in range(self.count()):
            namespace = self.string()
            rows = []
            for _ in range(self.count()):
                key = self.string()
                crc = self.take(4)
                value = self.string()
                rows.append([key, crc, value])
            self.namespaces.append((namespace, rows))
        if self.pos != len(data):
            raise ValueError('Trailing/unrecognized locres data')

    def take(self, size):
        value = self.data[self.pos:self.pos + size]
        if len(value) != size:
            raise ValueError('Truncated locres')
        self.pos += size
        return value

    def integer(self):
        return struct.unpack('<i', self.take(4))[0]

    def count(self):
        value = self.integer()
        if not 0 <= value <= 1000000:
            raise ValueError('Invalid locres count')
        return value

    def string(self):
        length = self.integer()
        if abs(length) > 1000000:
            raise ValueError('Invalid FString length')
        if not length:
            return ''
        value = self.take(abs(length) * (2 if length < 0 else 1))
        value = value.decode('utf-16-le' if length < 0 else 'utf-8')
        if not value.endswith('\0') or '\0' in value[:-1]:
            raise ValueError('Malformed FString terminator')
        return value[:-1]

    @staticmethod
    def encode_string(value):
        if '\0' in value:
            raise ValueError('Embedded null in locres string')
        if value.isascii():
            raw = value.encode('ascii') + b'\0'
            return struct.pack('<i', len(raw)) + raw
        raw = value.encode('utf-16-le') + b'\0\0'
        return struct.pack('<i', -len(raw) // 2) + raw

    def encode(self):
        parts = [struct.pack('<i', len(self.namespaces))]
        for namespace, rows in self.namespaces:
            parts.extend([self.encode_string(namespace), struct.pack('<i', len(rows))])
            for key, crc, value in rows:
                parts.extend([self.encode_string(key), crc, self.encode_string(value)])
        return b''.join(parts)


def build(verify_source, output):
    stem = ROOT / (ROOT.name + '_text')
    source = stem.with_suffix('.csv')
    target = source if verify_source else ROOT / (ROOT.name + '_text_translated.csv')
    if not verify_source:
        validation = json.loads((ROOT / 'TranslateFiles/reports/final_validation.json').read_text(encoding='utf-8'))
        if (validation.get('status') != 'passed'
                or validation.get('source_sha256') != hashlib.sha256(source.read_bytes()).hexdigest()
                or validation.get('translation_sha256') != hashlib.sha256(target.read_bytes()).hexdigest()):
            raise ValueError('Official translation export validation is missing or stale')
    resolver = ResourceResolver(source, target, mapping_path=stem.with_suffix('.mapping.json'))
    extraction = json.loads((ROOT / 'Analysis/extraction-report.json').read_text(encoding='utf-8'))
    for relative, expected in extraction['inputs'].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('Original resource hash changed: ' + relative)
    base = ROOT / 'Analysis/extracted'
    prefix = 'PsychonautsInTheRhombusOfRuin/Content/'
    json_rel = prefix + 'Dialog/Linecodes/MainGame_enUS.json'
    loc_rel = prefix + 'Localization/Game/en/Game.locres'
    original_dialogue = json.loads((base / json_rel).read_text(encoding='utf-8-sig'))
    dialogue = json.loads(json.dumps(original_dialogue))
    locres = Locres((base / loc_rel).read_bytes())
    original_locres = Locres((base / loc_rel).read_bytes())
    plans = []
    for key, entry in dialogue['LineCodeData'].items():
        if key == 'CMAP001TEXT' or not entry['Text'].strip():
            continue
        locator = json_rel + '#LineCodeData/' + key + '/Text'
        target_text = resolver.resolve(locator, entry['Text'])
        if text_sha(entry['Text']) != text_sha(resolver.sources[resolver.mapping[locator]]):
            raise ValueError('Exact source mismatch: ' + locator)
        entry['Text'] = target_text
        plans.append((locator, target_text))
    for namespace, rows in locres.namespaces:
        for row in rows:
            key, crc, value = row
            if not value.strip():
                continue
            locator = loc_rel + '#' + namespace + '/' + key
            target_text = resolver.resolve(locator, value)
            if text_sha(value) != text_sha(resolver.sources[resolver.mapping[locator]]):
                raise ValueError('Exact source mismatch: ' + locator)
            row[2] = target_text
            plans.append((locator, target_text))
    resolver.finish()  # Complete preflight before any output directory/file exists.
    encoded_json = (json.dumps(dialogue, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    encoded_locres = locres.encode()
    reread = Locres(encoded_locres)
    if reread.namespaces != locres.namespaces:
        raise ValueError('Locres round-trip mismatch')
    if json.loads(encoded_json) != dialogue:
        raise ValueError('JSON round-trip mismatch')
    if verify_source and (dialogue != original_dialogue or reread.namespaces != original_locres.namespaces):
        raise ValueError('Source identity verification changed resource semantics')
    output = output.resolve()
    if output == ROOT or output.is_relative_to((ROOT / 'Game').resolve()) or output.exists():
        raise ValueError('Output must be a new directory outside Game/')
    payload = {json_rel: encoded_json, loc_rel: encoded_locres}
    report = dict(mode='source_identity_only' if verify_source else 'translated_payload',
                  occurrences=len(plans), source_csv_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  translation_csv_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                  locres_crc_and_keys_preserved=True, in_game_check='pending',
                  files={key: dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
                         for key, data in payload.items()})
    for relative, data in payload.items():
        path = output / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (output / 'repack-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-source', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.verify_source, args.out)
