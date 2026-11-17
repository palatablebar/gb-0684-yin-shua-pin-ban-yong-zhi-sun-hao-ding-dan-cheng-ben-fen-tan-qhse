import io,csv,json,hashlib

def bundle(state):
    out=io.StringIO(newline='');writer=csv.writer(out)
    writer.writerow(['记录类型','批次','来源行','业务ID','原因码','内容'])
    rid=state.get('run_id','preview')
    writer.writerow(['运行清单',rid,'','','',json.dumps(state.get('manifest',{}),ensure_ascii=False,sort_keys=True)])
    writer.writerow(['对账',rid,'','','',json.dumps(state.get('reconcile',{}),ensure_ascii=False,sort_keys=True)])
    for row in state.get('calculations',[]):writer.writerow(['计算',rid,row.get('line',''),row.get('id',''),row.get('code',''),json.dumps(row,ensure_ascii=False,sort_keys=True)])
    for row in state['quarantine']:writer.writerow(['隔离',rid,row['line'],row.get('id',''),row['code'],json.dumps(row.get('raw',{}),ensure_ascii=False,sort_keys=True)])
    return '\ufeff'+out.getvalue()

def checksum(state):
    return hashlib.sha256(bundle(state).encode('utf-8')).hexdigest()

def revision_bundle(state):
    """修订结算归档：与普通封存同表头、同口径，新增调整/对比记录类型。"""
    out=io.StringIO(newline='');writer=csv.writer(out)
    writer.writerow(['记录类型','批次','来源行','业务ID','原因码','内容'])
    rid=state.get('run_id','preview');base=state.get('base_run_id',state.get('revision_summary',{}).get('base_run_id',''))
    manifest=dict(state.get('manifest',{}));manifest['base_run_id']=base;manifest['route_chosen']='ADJUST'
    writer.writerow(['运行清单',rid,'','','',json.dumps(manifest,ensure_ascii=False,sort_keys=True)])
    writer.writerow(['对账',rid,'','','',json.dumps(state.get('reconcile',{}),ensure_ascii=False,sort_keys=True)])
    writer.writerow(['修订汇总',rid,'','','',json.dumps(state.get('revision_summary',{}),ensure_ascii=False,sort_keys=True)])
    for row in state.get('adjustments',[]):
        writer.writerow(['调整',rid,row.get('line',''),row.get('id',''),row.get('code',''),json.dumps(row,ensure_ascii=False,sort_keys=True)])
    for lot in state.get('lot_adjustments',[]):
        writer.writerow(['纸批差额',rid,'',lot.get('id',''),'',json.dumps(lot,ensure_ascii=False,sort_keys=True)])
    for cmp in state.get('reopen_comparison',[]):
        writer.writerow(['重开对比',rid,'',cmp.get('lot',''),'REOPEN_VIEW_ONLY',json.dumps(cmp,ensure_ascii=False,sort_keys=True)])
    for row in state.get('quarantine',[]):
        writer.writerow(['隔离',rid,row.get('line',''),row.get('id',''),row.get('code',''),json.dumps(row.get('raw',{}),ensure_ascii=False,sort_keys=True)])
    return '﻿'+out.getvalue()

def revision_checksum(state):
    return hashlib.sha256(revision_bundle(state).encode('utf-8')).hexdigest()
