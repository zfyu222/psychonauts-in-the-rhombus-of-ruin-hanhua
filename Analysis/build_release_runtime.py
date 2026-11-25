"""Assemble the reviewed UE runtime resources into a separate offline PAK."""

import hashlib
import json
import subprocess
from pathlib import Path

from repack_text import Locres

ANALYSIS = Path(__file__).resolve().parent
PROJECT = ANALYSIS.parent
REPAK = PROJECT.parents[1] / 'Tools/repak/repak.exe'
CONTENT = Path('PsychonautsInTheRhombusOfRuin/Content')
LOCRES = CONTENT / 'Localization/Game/en/Game.locres'
DIALOGUE = CONTENT / 'Dialog/Linecodes/MainGame_enUS.json'
FONT_PATHS = {
    'PsychonautsDistanceField': CONTENT / 'UI/Fonts/PsychonautsDistanceField.uasset',
    'SubtitleFontDistanceField': CONTENT / 'Subtitles/SubtitleFontDistanceField.uasset',
}


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def digest(data):
    return hashlib.sha256(data).hexdigest()


def checked(path, expected):
    data = path.read_bytes()
    if digest(data) != expected:
        raise ValueError(f'Unexpected SHA256 for {path}')
    return data


def rows(locres):
    flattened = {(ns, key): (crc, text) for ns, entries in locres.namespaces for key, crc, text in entries}
    if len(flattened) != sum(len(entries) for _, entries in locres.namespaces):
        raise ValueError('Duplicate localization key')
    return flattened


def main():
    out = PROJECT / 'ImagePatch/release-runtime-v1'
    if out.exists():
        raise FileExistsError(out)
    dialogue_dir = ANALYSIS / 'translated-text-payload-v1'
    dialogue_report = read_json(dialogue_dir / 'repack-report.json')
    final = read_json(PROJECT / 'TranslateFiles/reports/final_validation.json')
    if final['status'] != 'passed' or final['translation_sha256'] != dialogue_report['translation_csv_sha256']:
        raise ValueError('Dialogue payload differs from the current formal translation')
    checked(PROJECT / f'{PROJECT.name}_text_translated.csv', final['translation_sha256'])
    files = {DIALOGUE: checked(dialogue_dir / DIALOGUE, dialogue_report['files'][DIALOGUE.as_posix()]['sha256'])}
    menu = Locres(checked(ANALYSIS / 'translated-menu-payload-v1' / LOCRES,
                          '4532c3e8bf2ed59443b7a476b2e576f64e6ce9efe3259876265e070588a0a26a'))
    test = read_json(ANALYSIS / 'headset-dialog-test-v1-report.json')
    test_locres = Locres(checked((PROJECT / test['pak']).parent / 'payload' / LOCRES,
                                 test['files'][LOCRES.as_posix()]))
    before = rows(menu)
    additions = {key: value for key, value in rows(test_locres).items()
                 if key[1] in test['added_test_translations']}
    if len(additions) != 3 or before.keys() & additions.keys():
        raise ValueError('Unexpected headset keys or conflict with menu keys')
    namespaces = dict(menu.namespaces)
    for (namespace, key), (crc, text) in additions.items():
        if text != test['added_test_translations'][key]:
            raise ValueError('Headset translation differs from the tested text')
        namespaces.setdefault(namespace, []).append([key, crc, text])
    menu.namespaces = list(namespaces.items())
    files[LOCRES] = menu.encode()
    if rows(Locres(files[LOCRES])) != before | additions:
        raise ValueError('Merged locres round-trip mismatch')
    for record in read_json(ANALYSIS / 'formal-fonts-v1/report.json')['fonts']:
        name = record['font']
        font_dir = ANALYSIS / 'formal-fonts-v1' / name
        data = checked(font_dir / 'fixed/fixed.uasset', record['sha256'])
        if data != (font_dir / 'verify/fixed.uasset').read_bytes():
            raise ValueError(f'Font round-trip mismatch: {name}')
        files[FONT_PATHS[name]] = data
    if set(files) != {DIALOGUE, LOCRES, *FONT_PATHS.values()}:
        raise ValueError('Unexpected runtime resource inventory')
    for relative, data in files.items():
        target = out / 'payload' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    pak = out / 'PsychonautsInTheRhombusOfRuin-1zh_CN_Runtime_P.pak'
    subprocess.run([REPAK, 'pack', out / 'payload', pak, '--version', 'V3',
                    '--mount-point', '../../../', '--quiet'], check=True)
    listed = subprocess.check_output([REPAK, 'list', pak]).decode().splitlines()
    if sorted(listed) != sorted(path.as_posix() for path in files):
        raise ValueError('Unexpected runtime PAK entries')
    for relative, data in files.items():
        if subprocess.check_output([REPAK, 'get', pak, relative.as_posix()]) != data:
            raise ValueError(f'PAK read-back mismatch: {relative}')
    report = {
        'status': 'offline_candidate',
        'pak': pak.relative_to(PROJECT).as_posix(),
        'pak_sha256': digest(pak.read_bytes()),
        'files': {path.as_posix(): digest(data) for path, data in files.items()},
        'locres_keys': len(before) + len(additions),
        'runtime_validation': 'pending',
        'dialogue_quality_report_hash': final['quality_review']['report_hash'],
    }
    (out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
