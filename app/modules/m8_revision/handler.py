from flask import Blueprint,request,render_template,jsonify
from app.web import page as _page
from app.errors import DomainError
from app.workflow import run_revision,load_revision
from app import store
from app.config import TITLE,MODULES,SHORT

bp=Blueprint('m8_revision',__name__)

def _payload():
    data=request.get_json(silent=True) or {}
    if not isinstance(data,dict):raise DomainError('PAYLOAD','请求必须是对象')
    base_id=data.get('base_run_id') or request.args.get('base_run_id')
    if base_id:
        baseline=store.get(base_id)
    else:
        # 缺省取最近一份已放行且对账平衡的批次作为基线
        baseline=None
        for h in store.history():
            cand=store.get(h['id'])
            if cand.get('decision')=='通过' and cand.get('reconcile',{}).get('balanced') \
               and cand.get('manifest',{}).get('kind')!='REVISION_SETTLEMENT':
                baseline=cand;break
        if baseline is None:raise DomainError('BASELINE','请指定已放行的基线批次')
    sample=data.get('sample',request.args.get('sample','revision_qty.csv'))
    if 'csv' in data:
        if not isinstance(data['csv'],str):raise DomainError('CSV','CSV内容必须是文本')
        content=data['csv'].encode()
    else:
        content=load_revision(sample)
    return content,baseline,data.get('parameters',{})

@bp.get('/m8_revision')
def screen():
    history=store.history()
    base=store.get(history[0]['id']) if history else None
    revision=None
    for h in history:
        cand=store.get(h['id'])
        if cand.get('manifest',{}).get('kind')=='REVISION_SETTLEMENT':
            revision=cand;break
    skeleton={'run_id':'（暂无批次）','manifest':{'generated_at':'','rule_version':'-','parameters':{}},
        'rows':[],'quarantine':[],'business':None}
    data=revision or skeleton
    run_ctx=revision or base or skeleton
    return render_template('m8_revision.html',title=TITLE,short=SHORT,modules=MODULES,current=8,
        data=data,run=run_ctx,history=history,base=base,revision=revision)

@bp.route('/api/m8_revision',methods=['GET','POST'])
def preview():
    try:
        content,baseline,params=_payload()
    except DomainError:
        if request.method=='GET':
            return jsonify({'adjustments':[],'lot_adjustments':[],'reopen_comparison':[],
                'quarantine':[],'revision_summary':None,'reconcile':{'balanced':False},
                'notice':'尚无已放行基线批，先在批次归档放行后再预演修订结算'})
        raise
    return jsonify(run_revision(content,baseline,params))

@bp.post('/api/revision_runs')
def submit():
    content,baseline,params=_payload()
    state=run_revision(content,baseline,params)
    return jsonify(store.save_revision(state))
