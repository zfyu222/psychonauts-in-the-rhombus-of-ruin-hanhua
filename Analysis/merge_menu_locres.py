"""Merge formally validated menu keys into the repacked en/Game.locres payload."""
import argparse
import hashlib
import json
import struct
import zlib
from pathlib import Path

from repack_text import Locres
from workflow_resource_occurrences import ResourceResolver, text_sha

ROOT=Path(__file__).resolve().parents[1]


def main(base_locres, out, base_report=None, verify_original_base=False):
    if out.exists():raise FileExistsError(out)
    child=ROOT/'TranslateFiles/ui-text'
    source=child/(ROOT.name+'_ui_text.csv')
    target=source.with_name(source.stem+'_translated.csv')
    validation=json.loads((child/'TranslateFiles/reports/final_validation.json').read_text(encoding='utf-8'))
    if (validation.get('status')!='passed' or validation['source_sha256']!=hashlib.sha256(source.read_bytes()).hexdigest()
            or validation['translation_sha256']!=hashlib.sha256(target.read_bytes()).hexdigest()):
        raise ValueError('Supplemental UI export validation is missing or stale')
    base_hash=hashlib.sha256(base_locres.read_bytes()).hexdigest()
    if verify_original_base:
        extraction=json.loads((ROOT/'Analysis/extraction-report.json').read_text(encoding='utf-8'))
        expected=next(v for k,v in extraction['inputs'].items() if k.endswith('Game.locres'))
        if base_hash!=expected:raise ValueError('Original-base test requires the exact extracted locres')
    else:
        if base_report is None:raise ValueError('Use --base-report for the validated repacked text payload')
        report=json.loads(base_report.read_text(encoding='utf-8'))
        main_csv=ROOT/(ROOT.name+'_text_translated.csv')
        expected=report['files']['PsychonautsInTheRhombusOfRuin/Content/Localization/Game/en/Game.locres']['sha256']
        if (report.get('mode')!='translated_payload' or base_hash!=expected
                or report['translation_csv_sha256']!=hashlib.sha256(main_csv.read_bytes()).hexdigest()):
            raise ValueError('Base locres is not the current repacked formal text payload')
    resolver=ResourceResolver(source,target,mapping_path=source.with_suffix('.mapping.json'))
    keys=json.loads((child/'localization_keys.json').read_text(encoding='utf-8'))['records']
    base=Locres(base_locres.read_bytes())
    original={(ns,key):(crc,value) for ns,rows in base.namespaces for key,crc,value in rows}
    if len(original)!=sum(len(rows) for ns,rows in base.namespaces):raise ValueError('Duplicate base localization keys')
    planned={}
    for row in keys:
        source_text=resolver.sources[row['ordinal']-1]
        if text_sha(source_text)!=row['source_sha256']:raise ValueError('UI source hash changed')
        localized=resolver.resolve(row['resource'],source_text)
        # UTF-32LE CRC matches 82/83 existing en text values; the remaining
        # "Translated Health!" test entry has an unknown original source/CRC.
        crc=struct.pack('<I',zlib.crc32(source_text.encode('utf-32-le')))
        key=(row['namespace'],row['key'])
        value=(crc,localized)
        if key in planned and planned[key]!=value:raise ValueError('Conflicting translations for one localization key')
        if key in original and original[key]!=value:raise ValueError('New menu key conflicts with base locres')
        planned[key]=value
    resolver.finish()
    merged={ns:[list(row) for row in rows] for ns,rows in base.namespaces}
    for (ns,key),(crc,value) in planned.items():
        if (ns,key) not in original:merged.setdefault(ns,[]).append([key,crc,value])
    base.namespaces=list(merged.items())
    data=base.encode();roundtrip=Locres(data)
    if roundtrip.namespaces!=base.namespaces:raise ValueError('Merged locres roundtrip failed')
    resulting={(ns,key):(crc,value) for ns,rows in roundtrip.namespaces for key,crc,value in rows}
    if any(resulting[key]!=value for key,value in original.items()):raise ValueError('Existing localization entry changed')
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(data)
    print(json.dumps(dict(menu_occurrences=len(keys),unique_menu_keys=len(planned),base_keys=len(original),
        output_keys=len(resulting),sha256=hashlib.sha256(data).hexdigest(),installed=False,
        mode='original_base_test' if verify_original_base else 'translated_payload')))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-locres',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--base-report',type=Path)
    parser.add_argument('--verify-original-base',action='store_true')
    args=parser.parse_args();main(args.base_locres,args.out,args.base_report,args.verify_original_base)
