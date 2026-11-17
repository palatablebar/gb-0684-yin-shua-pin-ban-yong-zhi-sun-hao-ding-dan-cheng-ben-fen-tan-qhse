from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from collections import defaultdict
from copy import deepcopy
from app.errors import DomainError
from app.config import REVISABLE
from app.modules.m4_segments.rules import losses
from app.modules.m5_calculate.rules import apply as m5_apply

# 参与核算的可修订字段（note 仅备注，不触发调整行）
REVISABLE_NUMERIC=frozenset(k for k in REVISABLE if k!='note')

# 与 m5 同口径的最大余数分摊，但允许带符号（减量时为负权重）。
# 先按符号方向各自向下取整到分，再把缺/溢的分币按最大余数补回，
# 保证 sum(分摊差额) == 批级精确差额四舍五入到分。
def signed_apportion(weights):
    weights=[Decimal(str(w)) for w in weights]
    target=sum(weights,Decimal(0)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    allocated=[w.quantize(Decimal('.01'),rounding=ROUND_DOWN) for w in weights]
    pennies=int((target-sum(allocated,Decimal(0)))/Decimal('.01'))
    order=sorted(range(len(weights)),key=lambda i:(-(weights[i]-allocated[i]),i))
    if pennies>=0:
        for i in order[:pennies]:allocated[i]+=Decimal('.01')
    else:
        # 负向缺口：余数最小（最负）的先减
        for i in order[-(-pennies):]:allocated[i]-=Decimal('.01')
    return allocated

def _d(v):return Decimal(str(v))

def _index_baseline(baseline):
    if not baseline.get('reconcile',{}).get('balanced'):
        raise DomainError('REVIEW_BASE','基线批对账未平衡，不能作为修订结算基线')
    if baseline.get('decision')!='通过':
        raise DomainError('REVIEW_BASE','基线批尚未放行，修订结算要求先放行旧批')
    orders={c['id']:c for c in baseline['calculations'] if c['code']=='RELEASED'}
    demands={d['id']:d for d in baseline['demands']}
    lots={l['id']:l for l in baseline['lots']}
    sources={d['id']:d['source'] for d in baseline['demands']}
    return orders,demands,lots,sources

def _contract(r):
    return tuple(str(r[k]) for k in ('lot','paper_w','paper_h','piece_w','piece_h','bleed',
        'gap','dimension_unit','grain','gsm','price_kg','fixed_loss','loss_pct'))

def _weight(sheets,paper_w,paper_h,gsm):
    return Decimal(sheets)*_d(paper_w)*_d(paper_h)/1000000*_d(gsm)/1000

def _revised_demand(d):
    r=d['source']
    return losses(r['quantity'],d['choice']['copies'],r['fixed_loss'],r['loss_pct'])

def settle(rev_state,baseline):
    base_orders,base_demands,base_lots,_=_index_baseline(baseline)
    rev_state=deepcopy(rev_state)
    quarantine=list(rev_state.get('quarantine',[]))
    # 按纸批聚合修订需求，材质契约必须与基线一致，否则隔离（不得借修订改材质/尺寸）。
    grouped=defaultdict(list)
    rejected=set()
    for d in rev_state['demands']:
        oid=d['id'];r=d['source']
        base=base_demands.get(oid)
        if base is not None and _contract(r)!=_contract(base['source']):
            # 材质/尺寸变更破坏原批成本口径，优先级最高：借修订改材质一律隔离
            quarantine.append({'line':d.get('line',''),'id':oid,'code':'MATERIAL','raw':r})
            rejected.add(oid);continue
        if base is None:
            quarantine.append({'line':d.get('line',''),'id':oid,'code':'BASELINE','raw':r})
            rejected.add(oid);continue
        changed=sorted(k for k in REVISABLE_NUMERIC if str(base['source'].get(k,''))!=str(r.get(k,'')))
        if not changed:
            quarantine.append({'line':d.get('line',''),'id':oid,'code':'NO_CHANGE','raw':r})
            continue  # 仅备注差异、无核算字段/交期变更：不产生调整行，也不占用库存
        d['_changed']=changed
        grouped[r['lot']].append(d)
    rev_state['_revision_input_count']=len(rev_state['demands'])

    adjustments=[];lot_summaries=[];comparisons=[]
    # 可排库存 = 基线批期末（完整原纸余料）。减量先释放、增量再扣减，按 due/order_id 排序。
    available={lid:int(l['closing']) for lid,l in base_lots.items()}
    for lot in sorted(grouped):
        if lot not in base_lots:
            raise DomainError('BASELINE','修订引用了基线不存在的纸批 %s'%lot)
        lot_base=base_lots[lot];stock0=available[lot];stock=stock0
        pending=[];exact_delta=[]
        for d in sorted(grouped[lot],key=lambda x:(x['due'],x['id'])):
            oid=d['id'];b=base_orders[oid];new=_revised_demand(d)
            sheet_delta=int(new['gross'])-int(b['gross'])
            # 增量（含减量后又被后续增量占用）受当前可排库存约束；库存不得为负。
            projected=stock-sheet_delta
            enough=projected>=0
            if not enough:
                quarantine.append({'line':d.get('line',''),'id':oid,'code':'REV_SHORTAGE','raw':d['source']})
                rejected.add(oid);continue
            weight_delta=_weight(sheet_delta,d['dims']['paper_w'],d['dims']['paper_h'],d['source']['gsm'])
            exact_cost_delta=weight_delta*_d(d['source']['price_kg'])
            pending.append((d,b,new,sheet_delta,weight_delta,exact_cost_delta))
            exact_delta.append(exact_cost_delta);stock=projected
        costs=signed_apportion(exact_delta)
        lot_cost_delta=Decimal('0.00');lot_sheet_delta=0;lot_weight_delta=Decimal('0')
        for (d,b,new,sheet_delta,weight_delta,_),cost in zip(pending,costs):
            # 期初=基线期末+本批此前累计调整；负向调整表现为退库（closing 上升）
            row_open=stock0+lot_sheet_delta
            item={'id':d['id'],'line':d.get('line',''),'lot':lot,'changed':d['_changed'],
                'base_version':str(b.get('version','1')),'revised_version':str(d['source']['version']),
                'base_gross':int(b['gross']),'revised_gross':int(new['gross']),'sheet_delta':sheet_delta,
                'base_due':base_demands[d['id']]['due'],'revised_due':d['due'],
                'opening':row_open,'closing':row_open-sheet_delta,
                'weight_delta_kg':str(weight_delta),'base_cost':b['cost'],'cost_delta':str(cost),
                'revised_cost':str((_d(b['cost'])+cost).quantize(Decimal('.01'))),
                'code':'ADJUST_RELEASED'}
            adjustments.append(item)
            lot_cost_delta+=cost;lot_sheet_delta+=sheet_delta;lot_weight_delta+=weight_delta
        lot_summaries.append({'id':lot,'base_closing':lot_base['closing'],
            'available':stock0,'sheet_delta':lot_sheet_delta,'revised_closing':stock0+lot_sheet_delta,
            'base_cost':lot_base['cost'],'cost_delta':str(lot_cost_delta.quantize(Decimal('.01'))),
            'weight_delta_kg':str(lot_weight_delta)})
        # 重开视角（REOPEN）：把修订需求当作全新一批，在基线期初库存上整批重算，仅供对比。
        comparisons.append(_reopen_view(lot,grouped[lot],baseline,base_orders))
        available[lot]=stock0+lot_sheet_delta

    rev_state['adjustments']=adjustments
    rev_state['lot_adjustments']=lot_summaries
    rev_state['reopen_comparison']=comparisons
    rev_state['quarantine']=quarantine
    rev_state['revision_summary']=_summary(baseline,adjustments,lot_summaries,comparisons,quarantine)
    return rev_state

def _reopen_view(lot,revision_demands,baseline,base_orders):
    # 以基线期初库存重放修订后的全量需求（同 lot 未修订订单保留基线口径），
    # 复用 m5 引擎，得到"若当初重开旧批"会得到的原单成本与库存。
    base_demands={d['id']:d for d in baseline['demands']}
    revised_ids={d['id'] for d in revision_demands}
    synthetic=deepcopy(baseline)
    demands=[]
    for d in baseline['demands']:
        if d['lot']!=lot:continue
        if d['id'] in revised_ids:
            rev=next(x for x in revision_demands if x['id']==d['id'])
            d=deepcopy(rev);d['_changed']=rev.get('_changed',[])
        demands.append(d)
    # m5 按全部 lot 分组，这里只保留本 lot 并恢复原始期初库存
    synthetic['demands']=[deepcopy(x) for x in demands]
    lot0=next(l for l in baseline['lots'] if l['id']==lot)
    for x in synthetic['demands']:x['source']['stock']=str(lot0['opening'])
    out=m5_apply(synthetic)
    rows=[c for c in out['calculations'] if c['lot']==lot]
    lot_row=next(l for l in out['lots'] if l['id']==lot)
    reopen_total=sum((_d(r['cost']) for r in rows),Decimal(0))
    base_total=sum((_d(base_orders[r['id']]['cost']) for r in rows if r['id'] in base_orders),Decimal(0))
    return {'lot':lot,'route':'REOPEN','opening':lot0['opening'],'closing':lot_row['closing'],
        'reopen_cost':str(reopen_total.quantize(Decimal('.01'))),
        'base_cost':str(base_total.quantize(Decimal('.01'))),
        'cost_vs_released':str((reopen_total-base_total).quantize(Decimal('.01'))),
        'orders':[{'id':r['id'],'gross':r['gross'],'cost':r['cost'],'code':r['code']} for r in rows]}

def _summary(baseline,adjustments,lot_summaries,comparisons,quarantine):
    total_delta=sum((_d(a['cost_delta']) for a in adjustments),Decimal(0)).quantize(Decimal('.01'))
    sheet_delta=sum(l['sheet_delta'] for l in lot_summaries)
    base_total=_d(baseline['business']['total'])
    # 重开路线若被错误采用，会改写的已放行金额（仅展示，绝不入账）
    reopen_rewrite=sum((_d(c['cost_vs_released']) for c in comparisons),Decimal(0)).quantize(Decimal('.01'))
    return {'base_run_id':baseline['run_id'],'base_decision':baseline['decision'],
        'base_total':str(base_total),'adjusted_total':str((base_total+total_delta).quantize(Decimal('.01'))),
        'cost_delta':str(total_delta),'sheet_delta':sheet_delta,
        'reopen_rewrite_if_chosen':str(reopen_rewrite),
        'released_amount_immutable':True,'adjusted_orders':len(adjustments),
        'quarantined':len(quarantine)}
