"""Extract displayed localized Kismet constants, not enum labels/internal IDs."""
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT.parents[1]/'Tools/localization'))
from workflow_resource_occurrences import export_occurrences

child=ROOT/'TranslateFiles/ui-text'
child.mkdir()  # Isolated: never changes the active 2694-record source.
records=[];context={};locators=[];excluded=[]
for name,relative in (
    ('StartScreen','PsychonautsInTheRhombusOfRuin/Content/Maps/StartScreen.umap'),
    ('PauseRoom','PsychonautsInTheRhombusOfRuin/Content/Gameplay/Environment/Menus/Pause/PauseRoom.uasset'),
):
    snapshot=ROOT/f'Analysis/menu-probe-v1/{name}/{name}.json'
    asset=json.loads(snapshot.read_text(encoding='utf-8-sig'))
    for index,export in enumerate(asset['Exports']):
        function=export['ObjectName']
        def walk(value,path):
            if isinstance(value,dict):
                if value.get('$type','').startswith('UAssetAPI.Kismet.Bytecode.FScriptText'):
                    source=value.get('LocalizedSource')
                    if source and source.get('Value'):
                        text=source['Value']
                        if (function not in ('CreateMenuItems','FuncAudioOptions','FuncVideoOptions')
                                or text=='Debug Warps' or re.fullmatch(r'(?:SYSTEM\d+TEXT|\d+%)',text)):
                            excluded.append(dict(resource=relative,path=path,source=text,reason='debug/dynamic percentage/internal linecode'))
                        else:
                            key=value['LocalizedKey']['Value']
                            namespace=value['LocalizedNamespace']['Value']
                            pointer='/Exports/'+str(index)+path+'/LocalizedSource/Value'
                            resource=relative+'#'+pointer
                            records.append(dict(resource=resource,source=text))
                            context[str(len(records))]=dict(resource=resource,text_type='UI',group=name,
                                note=f'Displayed menu label in {function}; preserve rich-text tags. Audio options are volume settings; Video options include resolution.')
                            locators.append(dict(ordinal=len(records),resource=resource,namespace=namespace,key=key,
                                source_sha256=hashlib.sha256(text.encode('utf-8')).hexdigest(),
                                source_crc32_encoding='utf-32-le',snapshot_sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest()))
                for key,item in value.items():walk(item,path+'/'+str(key))
            elif isinstance(value,list):
                for n,item in enumerate(value):walk(item,path+'/'+str(n))
        walk(export,'')
source=child/(ROOT.name+'_ui_text.csv')
export_occurrences(records,source,source.with_suffix('.mapping.json'))
source.with_suffix('.context.json').write_text(json.dumps(context,ensure_ascii=False,indent=2),encoding='utf-8')
(child/'localization_keys.json').write_text(json.dumps(dict(records=locators,excluded=excluded),ensure_ascii=False,indent=2),encoding='utf-8')
config=json.loads((ROOT/'TranslateFiles/image-text/input-config.json').read_text(encoding='utf-8'))
config['api']['max_requests']=min(20,config['api']['max_requests'])
config['style']='菜单和设置文字简短、自然、清晰。Voice为语音音量，SFX为音效，Video为画面设置；保留占位符与<br>等富文本标签。场景分组表示主菜单/暂停菜单，不将代码路径或功能名称当成待译正文。'
config['game_background']='Psychonauts in the Rhombus of Ruin（脑航员：菱形废墟），UE4.12.5 VR冒险游戏。本数据集是补充发现的主菜单与暂停菜单蓝图本地化文本。每条按资源字段独立保留；相邻CSV行不作为剧情上下文。'
(child/'input-config.json').write_text(json.dumps(config,ensure_ascii=False,indent=2),encoding='utf-8')
(child/'README.md').write_text('# Supplemental menu translation\n\nRead-only extraction from localized FScriptText constants in StartScreen and PauseRoom. Source and mapping are isolated from ongoing dialogue/image translation. Repack via localization keys and CRC, not Kismet bytecode edits.\n',encoding='utf-8')
print(json.dumps(dict(project=str(child),records=len(records),excluded=len(excluded),source=str(source),api_request_cap=config['api']['max_requests'])))
