import time,importlib,json,base64
from pathlib import Path
from app.config import MODULES
from app.errors import DomainError
from app.manifest import identity,manifest,revision_identity

def load(sample):
    if sample not in ('dirty.csv','clean.csv','legacy.csv'):raise DomainError('SAMPLE','样例名称无效')
    return (Path(__file__).resolve().parents[1]/'sample_data'/sample).read_bytes()

def run(content,parameters=None,stage=7):
    if len(content)>2_000_000:raise DomainError('SIZE','文件超过2MB',413)
    params=parameters or {}
    if not isinstance(params,dict):raise DomainError('PARAMETERS','参数必须是对象')
    start=time.monotonic();state=None
    for n,entry in enumerate(MODULES,1):
        if n>stage:break
        fn=importlib.import_module('app.modules.'+entry[0]+'.service').execute
        state=fn(content,params) if n==1 else fn(state)
    # Decimal values are serialized as strings before any storage or response.
    state=json.loads(json.dumps(state,default=str,ensure_ascii=False))
    state['run_id']=identity(content,params);state['manifest']=manifest(content,params,time.monotonic()-start)
    state['source_b64']=base64.b64encode(content).decode('ascii')
    if stage>=7:
        from app.modules.m7_archive.export_out import checksum
        state['archive']['sha256']=checksum(state)
    return state

def load_revision(sample):
    from app.config import REVISION_SAMPLES
    if sample not in REVISION_SAMPLES:raise DomainError('SAMPLE','修订样例名称无效')
    return (Path(__file__).resolve().parents[1]/'sample_data'/sample).read_bytes()

def run_revision(content, baseline, parameters=None):
    """迟到修订工单结算。基线批保持冻结，差额独立成单，重开视角仅作对比。"""
    if len(content)>2_000_000:raise DomainError('SIZE','文件超过2MB',413)
    params=parameters or {}
    start=time.monotonic()
    state=None
    for n in range(1,5):  # M1-M4：采信→换算→版本→损耗，得到修订需求
        entry=MODULES[n-1][0]
        fn=importlib.import_module('app.modules.'+entry+'.service').execute
        state=fn(content,params) if n==1 else fn(state)
    state['_baseline_state']=baseline
    state=importlib.import_module('app.modules.m8_revision.service').execute(state)
    from app.modules.m8_revision.reconcile import balance
    state['reconcile']=balance(state)
    state=json.loads(json.dumps(state,default=str,ensure_ascii=False))
    state['run_id']=revision_identity(baseline['run_id'],content,params)
    state['base_run_id']=baseline['run_id']
    state['manifest']=manifest(content,params,time.monotonic()-start)
    state['manifest']['kind']='REVISION_SETTLEMENT'
    state['source_b64']=base64.b64encode(content).decode('ascii')
    from app.modules.m7_archive.export_out import revision_checksum
    state['archive']={'sha256':revision_checksum(state),
        'evidence_count':len(state.get('adjustments',[]))+len(state.get('quarantine',[])),
        'ready':state['reconcile']['balanced']}
    return state
