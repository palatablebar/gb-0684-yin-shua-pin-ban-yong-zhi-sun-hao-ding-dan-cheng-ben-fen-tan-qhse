import csv,io
import pytest
from decimal import Decimal
from app.workflow import load,load_revision,run,run_revision
from app import store
from app.errors import DomainError
from app.modules.m7_archive.export_out import revision_bundle,revision_checksum
from app.modules.m8_revision.rules import signed_apportion

D=lambda x:Decimal(str(x))

@pytest.fixture
def released_base(tmp_path,monkeypatch):
    monkeypatch.setenv('DB_PATH',str(tmp_path/'r.db'))
    base=run(load('dirty.csv'),{})
    store.save(base['run_id'],base);store.review(base['run_id'],1,'通过')
    return store.get(base['run_id'])

# ---------- 纯函数：带符号最大余数分摊 ----------
def test_signed_apportion_positive_conserves_total():
    out=signed_apportion(['.3333']*3)
    assert out==[Decimal('.34'),Decimal('.33'),Decimal('.33')] and sum(out)==Decimal('1.00')

def test_signed_apportion_negative_conserves_total():
    out=signed_apportion(['-.3333','-.7171','-.2020'])
    assert sum(out)==Decimal('-1.25') and all(abs(v)<Decimal('1') for v in out)

def test_signed_apportion_mixed_signs():
    out=signed_apportion(['1.234','-0.567','2.891'])
    assert sum(out)==Decimal('3.56')

# ---------- 裁决核心：冻结旧批 + 差额独立 ----------
def test_baseline_amount_is_frozen(released_base):
    rv=run_revision(load_revision('revision_qty.csv'),released_base,{})
    # 旧批已放行金额原样保留，调整后总额 = 冻结额 + 本期差额
    assert rv['revision_summary']['base_total']==released_base['business']['total']
    assert rv['revision_summary']['released_amount_immutable'] is True
    assert D(rv['revision_summary']['adjusted_total'])==D(rv['revision_summary']['base_total'])+D(rv['revision_summary']['cost_delta'])

def test_decrease_returns_stock_and_negative_delta(released_base):
    rv=run_revision(load_revision('revision_qty.csv'),released_base,{})
    lot=next(l for l in rv['lot_adjustments'] if l['id']=='PAPER1')
    # 减量：期末回升、张数差为负、成本差额为负
    assert lot['sheet_delta']<0 and lot['revised_closing']==lot['base_closing']+lot['sheet_delta']
    assert D(lot['cost_delta'])<0
    assert all(a['closing']==a['opening']-a['sheet_delta'] for a in rv['adjustments'])

def test_due_only_revision_zero_delta_but_traced(released_base):
    rv=run_revision(load_revision('revision_due.csv'),released_base,{})
    a=rv['adjustments'][0]
    assert a['changed']==['due'] and a['sheet_delta']==0 and a['cost_delta']=='0.00'
    assert a['base_due']!=a['revised_due']
    assert rv['revision_summary']['cost_delta']=='0.00'

def test_increase_draws_available_stock(released_base):
    rv=run_revision(load_revision('revision_mix.csv'),released_base,{})
    inc=next(a for a in rv['adjustments'] if a['id']=='PO0001')
    assert inc['sheet_delta']>0 and inc['closing']==inc['opening']-inc['sheet_delta']
    # 可排库存起点是基线批期末余料
    assert inc['opening']==next(l for l in released_base['lots'] if l['id']=='PAPER1')['closing']

def test_stock_never_goes_negative(released_base):
    hdr='id,order_id,version,lot,paper_w,paper_h,piece_w,piece_h,bleed,gap,dimension_unit,grain,quantity,gsm,price_kg,fixed_loss,loss_pct,stock,due,note'
    # 远超可排库存（基线期末仅536张）的巨量增量
    huge=hdr+'\n00001,PO0001,2,PAPER1,1000,700,300,200,0,0,mm,any,999999,80,6.80,20,2,2000,2026-11-17,x'
    rv=run_revision(huge.encode(),released_base,{})
    assert any(q['code']=='REV_SHORTAGE' for q in rv['quarantine'])
    assert all(l['revised_closing']>=0 for l in rv['lot_adjustments'])

def test_material_change_is_quarantined_not_settled(released_base):
    rv=run_revision(load_revision('revision_mix.csv'),released_base,{})
    z=next(q for q in rv['quarantine'] if q['id']=='PO0003')
    assert z['code']=='MATERIAL'
    assert 'PO0003' not in [a['id'] for a in rv['adjustments']]

def test_unknown_order_is_baseline_quarantined(released_base):
    hdr='id,order_id,version,lot,paper_w,paper_h,piece_w,piece_h,bleed,gap,dimension_unit,grain,quantity,gsm,price_kg,fixed_loss,loss_pct,stock,due,note'
    unk=hdr+'\n00999,GHOST,2,PAPER1,1000,700,300,200,0,0,mm,any,1000,80,6.80,20,2,2000,2026-11-17,x'
    rv=run_revision(unk.encode(),released_base,{})
    assert any(q['id']=='GHOST' and q['code']=='BASELINE' for q in rv['quarantine'])

def test_unreleased_baseline_rejected(tmp_path,monkeypatch):
    monkeypatch.setenv('DB_PATH',str(tmp_path/'u.db'))
    base=run(load('dirty.csv'),{});store.save(base['run_id'],base)  # 未放行
    with pytest.raises(DomainError) as e:
        run_revision(load_revision('revision_qty.csv'),store.get(base['run_id']),{})
    assert e.value.code=='REVIEW_BASE'

# ---------- 两条路线：批级守恒、单单成本不同 ----------
def test_two_routes_diverge_on_per_order_cost_but_conserve_lot_total():
    hdr='id,order_id,version,lot,paper_w,paper_h,piece_w,piece_h,bleed,gap,dimension_unit,grain,quantity,gsm,price_kg,fixed_loss,loss_pct,stock,due,note'
    def row(i,o,q,v=1):return f'{i:05d},{o},{v},PAPER1,1000,700,300,200,0,0,mm,any,{q},80,6.83,20,2,2000,2026-11-{10+i},n'
    base=run(('\n'.join([hdr]+[row(i+1,f'PO{i+1}',q) for i,q in enumerate([1000,777,333,900,555])])).encode(),{})
    base['decision']='通过'
    rev='\n'.join([hdr,row(1,'PO1',500,2),row(2,'PO2',100,2),row(4,'PO4',250,2)])
    rv=run_revision(rev.encode(),base,{})
    adj={a['id']:a['revised_cost'] for a in rv['adjustments']}
    rop={o['id']:o['cost'] for o in rv['reopen_comparison'][0]['orders']}
    # 同单在两条路线下原单成本不同（分币落点不同）
    assert any(adj[k]!=rop[k] for k in adj)
    # 但批级总差额两条路线相等（守恒），重开视角仅作对比标记
    assert rv['revision_summary']['cost_delta']==rv['revision_summary']['reopen_rewrite_if_chosen']
    assert all(c['route']=='REOPEN' for c in rv['reopen_comparison'])

def test_reopen_view_does_not_mutate_baseline(released_base):
    before=released_base['business']['total']
    run_revision(load_revision('revision_qty.csv'),released_base,{})
    again=store.get(released_base['run_id'])
    assert again['business']['total']==before  # 基线库内金额绝不被改写

# ---------- 对账四勾稽 ----------
def test_reconcile_balanced_for_all_samples(released_base):
    for s in ('revision_qty.csv','revision_due.csv','revision_mix.csv'):
        rv=run_revision(load_revision(s),released_base,{})
        assert rv['reconcile']['balanced'] is True
        assert rv['reconcile']['finance_frozen_ok'] and rv['reconcile']['cost_balanced']
        assert rv['reconcile']['stock_balanced'] and rv['reconcile']['route_guarded']

def test_cost_delta_apportion_conservation(released_base):
    rv=run_revision(load_revision('revision_qty.csv'),released_base,{})
    rows=sum((D(a['cost_delta']) for a in rv['adjustments']),Decimal('0.00'))
    lots=sum((D(l['cost_delta']) for l in rv['lot_adjustments']),Decimal('0.00'))
    assert rows==lots==D(rv['revision_summary']['cost_delta'])

# ---------- 幂等：同修订重跑不新增差额 ----------
def test_same_revision_rerun_is_idempotent(released_base):
    a=store.save_revision(run_revision(load_revision('revision_qty.csv'),released_base,{}))
    n_before=len(store.history())
    b=store.save_revision(run_revision(load_revision('revision_qty.csv'),released_base,{}))
    assert a['run_id']==b['run_id'] and len(store.history())==n_before
    assert b['revision_summary']['cost_delta']==a['revision_summary']['cost_delta']

def test_distinct_revision_gets_distinct_run(released_base):
    a=store.save_revision(run_revision(load_revision('revision_qty.csv'),released_base,{}))
    b=store.save_revision(run_revision(load_revision('revision_mix.csv'),released_base,{}))
    assert a['run_id']!=b['run_id']

# ---------- 失败恢复旧版，不丢记录 ----------
def test_failed_save_rolls_back_and_keeps_previous(released_base,monkeypatch):
    good=run_revision(load_revision('revision_qty.csv'),released_base,{})
    saved=store.save_revision(good)
    bad=run_revision(load_revision('revision_mix.csv'),released_base,{})  # 先正常构建
    import app.modules.m7_archive.export_out as ex
    def boom(state):raise RuntimeError('disk full')
    monkeypatch.setattr(ex,'revision_checksum',boom)  # 仅让保存期指纹自检失败
    with pytest.raises(RuntimeError):store.save_revision(bad)
    # latest 仍是上一份成功结算，记录未丢
    assert store.history()[0]['id']==saved['run_id']
    monkeypatch.undo()

# ---------- 归档导出同口径 ----------
def test_revision_export_same_schema_and_checksum(released_base):
    rv=run_revision(load_revision('revision_mix.csv'),released_base,{})
    text=revision_bundle(revision_bundle and rv)
    rows=list(csv.reader(io.StringIO(text.lstrip('﻿'))))
    assert rows[0]==['记录类型','批次','来源行','业务ID','原因码','内容']
    kinds={r[0] for r in rows[1:]}
    assert {'运行清单','对账','修订汇总','调整','纸批差额','重开对比','隔离'}<=kinds
    assert revision_checksum(rv)==rv['archive']['sha256'] and len(rv['archive']['sha256'])==64

# ---------- HTTP 端到端 ----------
def test_revision_api_and_archive_download(client):
    base=client.post('/api/runs',json={'sample':'dirty.csv'}).get_json()
    client.post(f"/api/runs/{base['run_id']}/review",json={'version':1,'decision':'通过'})
    r=client.post('/api/revision_runs',json={'base_run_id':base['run_id'],'sample':'revision_qty.csv'})
    assert r.status_code==200
    rv=r.get_json()
    dl=client.get(f"/api/revision_archive/{rv['run_id']}/export.csv")
    assert dl.status_code==200 and '修订汇总' in dl.data.decode('utf-8-sig')

def test_revision_preview_requires_baseline(client):
    r=client.post('/api/m8_revision',json={'sample':'revision_qty.csv'})
    assert r.status_code==422 and r.get_json()['code']=='BASELINE'

def test_revision_page_renders(client):
    assert client.get('/m8_revision').status_code==200
