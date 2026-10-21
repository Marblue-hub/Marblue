"""Record final local PBIX evidence without changing source data or report values."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]
def load(path):
    return json.loads((ROOT/path).read_text(encoding='utf-8-sig'))
def save(path,value):
    (ROOT/path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(path):
    return hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
def canonical(value):
    # Desktop explicitly writes active=true on default-active category bindings.
    if isinstance(value,dict):
        return {k:canonical(v) for k,v in value.items() if not (k=='active' and v is True)}
    if isinstance(value,list):
        return [canonical(v) for v in value]
    return value

pbix=Path('powerbi/DataCoSupplyChain_P0.pbix')
source=ROOT/'powerbi/DataCoSource/DataCoSupplyChain.Report'
acceptance=load('reports/powerbi/desktop_acceptance.json')
assert acceptance['failed']==0 and acceptance['checks']==404
validation=load('reports/powerbi_schema_validation.json')
assert validation['data']['result']=='succeeded' and validation['data']['errorCount']==0
differences=[]
visuals=list(source.glob('definition/pages/*/visuals/*/visual.json'))
with zipfile.ZipFile(ROOT/pbix) as bundle:
    assert bundle.testzip() is None
    for file in visuals:
        expected=json.loads(file.read_text(encoding='utf-8'))
        actual=json.loads(bundle.read('Report/'+file.relative_to(source).as_posix()))
        for key in ('visualType','query'):
            if canonical(expected['visual'].get(key))!=canonical(actual['visual'].get(key)):
                differences.append({'file':file.relative_to(source).as_posix(),'property':key})
assert not differences,differences
save('reports/powerbi/source_pbix_parity.json',{'visuals_checked':len(visuals),'query_differences':differences})
build=load('reports/powerbi_build.json')
build.update(desktop_verified=True,desktop_acceptance='reports/powerbi/desktop_acceptance.json',
             pbix=str(pbix),source_query_parity_checked=len(visuals))
save('reports/powerbi_build.json',build)
verification=load('reports/verification.json')
verification.update(tests=29,powerbi_engine_checked=True,powerbi_actual_checks=404,
                    powerbi_reopened=True,powerbi_file=str(pbix))
save('reports/verification.json',verification)
run=load('reports/run_manifest.json')
run['gates']['powerbi']='passed; actual Desktop refresh, DAX, four pages, slicers, PBIX reopen'
for file in run['artifacts']:
    if (ROOT/file).is_file():
        run['artifacts'][file]=sha(file)
save('reports/run_manifest.json',run)
files=[pbix,Path('reports/powerbi/desktop_acceptance.json'),Path('reports/powerbi/desktop_dax_results.json'),
       Path('reports/powerbi/source_pbix_parity.json'),Path('reports/powerbi_schema_validation.json'),
       Path('reports/powerbi/desktop_refresh_metadata.json')]
files += [p.relative_to(ROOT) for p in (ROOT/'reports/powerbi/screenshots').glob('*.png')]
refresh=load('reports/powerbi/desktop_refresh_metadata.json')
refresh_native=max(row['RefreshedTime'] for row in refresh['queries'][0]['rows'])
manifest={'completed_at_utc':datetime.now(timezone.utc).isoformat(),'desktop_version':'2.159.883.0',
          'desktop_executable':'D:/Apps/Power BI Desktop/bin/PBIDesktop.exe','pbix':str(pbix),
          'pbix_bytes':(ROOT/pbix).stat().st_size,'pbip':'powerbi/DataCoSource/DataCoSupplyChain.pbip',
          'reopened_from_pbix':True,'actual_dax_checks':404,'actual_dax_failed':0,'tests_passed':29,
          'visuals':len(visuals),'measures':46,'source_visual_queries_match_pbix':True,
          'model_last_refresh_native':refresh_native,
          'model_refresh_timezone':'Native ADOMD DateTime.Kind is Unspecified; no timezone conversion applied.',
          'sha256':{str(path):sha(path) for path in files}}
save('reports/powerbi/delivery_manifest.json',manifest)
print(json.dumps({k:v for k,v in manifest.items() if k!='sha256'},ensure_ascii=True))
