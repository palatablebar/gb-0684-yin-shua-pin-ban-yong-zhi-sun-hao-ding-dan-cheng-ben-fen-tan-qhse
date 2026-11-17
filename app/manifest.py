import hashlib,json,time
from datetime import datetime,timezone
from app.config import RULE_VERSION

def identity(content, parameters):
    raw = content + json.dumps(parameters,sort_keys=True,ensure_ascii=False).encode() + RULE_VERSION.encode()
    return hashlib.sha256(raw).hexdigest()[:20]

def revision_identity(baseline_run_id, content, parameters):
    # 同一基线批 + 同一修订输入 + 同一规则版本，重跑得到同一结算单号（幂等，不新增差额）
    raw = baseline_run_id.encode() + content + json.dumps(parameters,sort_keys=True,ensure_ascii=False).encode() + RULE_VERSION.encode()
    return 'RV'+hashlib.sha256(raw).hexdigest()[:18]

def manifest(content, parameters, elapsed):
    return {'sha256':hashlib.sha256(content).hexdigest(),'rule_version':RULE_VERSION,
        'parameters':parameters,'elapsed_ms':round(elapsed*1000),
        'generated_at':datetime.now(timezone.utc).isoformat(),'timezone':'Asia/Shanghai'}
