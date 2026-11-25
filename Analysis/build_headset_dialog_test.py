"""Build an offline UE4 PAK to test the startup headset dialog in en culture."""

import base64
import hashlib
import json
import struct
import subprocess
import zlib
from pathlib import Path

from repack_text import Locres

ANALYSIS = Path(__file__).resolve().parent
PROJECT = ANALYSIS.parent
REPAK = PROJECT.parents[1] / 'Tools/repak/repak.exe'
CONTENT = Path('PsychonautsInTheRhombusOfRuin/Content')
LOCRES = CONTENT / 'Localization/Game/en/Game.locres'
FONT = CONTENT / 'UI/Fonts/PsychonautsDistanceField.uasset'
TRANSLATIONS = {
    '0366FD054EE4D0C8F1B1E6B2A57F7ADE': (
        '错误：未检测到 VR 头显。\r\n'
        '本游戏需要 VR 头显才能正常运行。\r\n'
        '请检查 VR 设置后重新启动游戏。'
    ),
    '33E513B34E9AE5CCBA62E0A83AF146F1': '退出',
    'B348E27B440BD0288A09139432964210': '头显追踪错误',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    out = PROJECT / 'ImagePatch/headset-dialog-test-v1'
    if out.exists():
        raise FileExistsError(out)
    evidence = json.loads((ANALYSIS / 'headset-dialog-localization-evidence-v1.json').read_text(encoding='utf-8'))
    probe = ANALYSIS / 'headset-dialog-probe-v1'
    source_asset = (probe / 'FirstPersonCharacter.uasset').read_bytes()
    if sha(source_asset) != evidence['asset_sha256']:
        raise ValueError('Source asset differs from the localization evidence')
    if source_asset != (probe / 'probe/FirstPersonCharacter.uasset').read_bytes():
        raise ValueError('Blueprint probe did not round-trip')
    snapshot = json.loads((probe / 'probe/FirstPersonCharacter.json').read_text(encoding='utf-8-sig'))
    entries = evidence['entries']
    if len(entries) != len(TRANSLATIONS) or {entry['key'] for entry in entries} != set(TRANSLATIONS):
        raise ValueError('Unexpected set of dialog keys')
    original = (ANALYSIS / 'extracted' / LOCRES).read_bytes()
    locres = Locres(original)
    before = {(ns, key): (crc, value) for ns, rows in locres.namespaces for key, crc, value in rows}
    namespaces = dict(locres.namespaces)
    additions = {}
    for entry in entries:
        value = snapshot
        for part in entry['json_pointer'].rsplit('/LocalizedSource/Value', 1)[0].split('/')[1:]:
            value = value[int(part)] if isinstance(value, list) else value[part]
        source = value['LocalizedSource']['Value']
        key = value['LocalizedKey']['Value']
        namespace = value['LocalizedNamespace']['Value']
        if (key, namespace, sha(source.encode())) != (entry['key'], entry['namespace'], entry['source_sha256']):
            raise ValueError('Dialog source or identity differs from the evidence')
        if (namespace, key) in before:
            raise ValueError('Dialog key already exists in the base localization')
        crc = struct.pack('<I', zlib.crc32(source.encode('utf-32-le')))
        additions[namespace, key] = (crc, TRANSLATIONS[key])
        namespaces.setdefault(namespace, []).append([key, crc, TRANSLATIONS[key]])
    locres.namespaces = list(namespaces.items())
    localized = locres.encode()
    reparsed = Locres(localized)
    after = {(ns, key): (crc, value) for ns, rows in reparsed.namespaces for key, crc, value in rows}
    if after != before | additions or reparsed.namespaces != locres.namespaces:
        raise ValueError('Localization round-trip differs from the intended records')

    font_dir = ANALYSIS / 'formal-fonts-v1/PsychonautsDistanceField'
    font = (font_dir / 'fixed/fixed.uasset').read_bytes()
    if font != (font_dir / 'verify/fixed.uasset').read_bytes():
        raise ValueError('Font round-trip mismatch')
    parsed = json.loads((font_dir / 'verify/fixed.json').read_text(encoding='utf-8-sig'))
    remap = base64.b64decode(parsed['Exports'][0]['Extras'])
    count = struct.unpack_from('<i', remap)[0]
    mapped = {struct.unpack_from('<HH', remap, 4 + i * 4)[0] for i in range(count)}
    missing = {c for text in TRANSLATIONS.values() for c in text if not c.isspace() and ord(c) not in mapped}
    if missing:
        raise ValueError(f'Missing font glyphs: {ascii(missing)}')

    files = {LOCRES: localized, FONT: font}
    for relative, data in files.items():
        path = out / 'payload' / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    pak = out / 'PsychonautsInTheRhombusOfRuin-1zh_HeadsetTest_P.pak'
    subprocess.run([REPAK, 'pack', out / 'payload', pak, '--version', 'V3', '--mount-point', '../../../', '--quiet'], check=True)
    listed = subprocess.check_output([REPAK, 'list', pak]).decode().splitlines()
    if sorted(listed) != sorted(path.as_posix() for path in files):
        raise ValueError('Unexpected PAK entries')
    for relative, data in files.items():
        if subprocess.check_output([REPAK, 'get', pak, relative.as_posix()]) != data:
            raise ValueError(f'PAK read-back differs: {relative}')
    report = {
        'status': 'offline_test_candidate',
        'target_culture': 'en',
        'runtime_culture_verified': False,
        'base_locres_sha256': sha(original),
        'existing_locres_keys_preserved': len(before),
        'added_test_translations': TRANSLATIONS,
        'font_mapped_characters': count,
        'missing_test_glyphs': [],
        'files': {path.as_posix(): sha(data) for path, data in files.items()},
        'pak': pak.relative_to(PROJECT).as_posix(),
        'pak_sha256': sha(pak.read_bytes()),
        'installed': False,
    }
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
