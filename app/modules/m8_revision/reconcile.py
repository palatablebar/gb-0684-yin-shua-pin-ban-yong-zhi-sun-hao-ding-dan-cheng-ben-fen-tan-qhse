from decimal import Decimal

def _d(v):return Decimal(str(v))

def balance(state):
    """修订结算对账：四条独立勾稽，任一不平则整单不得放行。"""
    base_total=_d(state['revision_summary']['base_total'])
    delta_total=_d(state['revision_summary']['cost_delta'])
    adj_total=sum((_d(a['cost_delta']) for a in state['adjustments']),Decimal('0.00'))
    lot_delta=sum((_d(l['cost_delta']) for l in state['lot_adjustments']),Decimal('0.00'))
    # 1) 财务：已放行金额冻结，调整后总额 = 旧批冻结额 + 本期差额（差额独立入账）
    finance_ok=state['revision_summary']['adjusted_total']==str((base_total+delta_total).quantize(Decimal('.01')))
    cost_conserved=adj_total==lot_delta==delta_total
    # 2) 库存：每批 修订后期末 = 基线期末 + 本期张数差；调整行逐行 opening-closing=gross 差
    stock_rows=all((a['opening']-a['closing'])==a['sheet_delta'] for a in state['adjustments'])
    stock_lots=all(l['revised_closing']==l['base_closing']+l['sheet_delta'] for l in state['lot_adjustments'])
    no_negative=all(l['revised_closing']>=0 for l in state['lot_adjustments'])
    # 3) 路线：重开视角的改写金额独立列示，默认路线绝不改写已放行金额
    route_guarded=state['revision_summary']['released_amount_immutable'] is True
    # 4) 隔离修订不参与结算：修订输入数 = 采纳调整 + 全部隔离（含材质/缺基线/缺纸/无变更）
    accepted=len(state['adjustments']);quarantined=state['revision_summary']['quarantined']
    accounted=accepted+quarantined==state.get('_revision_input_count',len(state['demands']))
    balanced=all([finance_ok,cost_conserved,stock_rows,stock_lots,no_negative,route_guarded,accounted])
    return {'base_run_id':state['revision_summary']['base_run_id'],
        'finance_frozen_ok':finance_ok,'cost_balanced':cost_conserved,
        'stock_balanced':stock_rows and stock_lots,'stock_non_negative':no_negative,
        'route_guarded':route_guarded,'accounted':accounted,'balanced':balanced,
        'accepted':accepted,'quarantined':quarantined}
