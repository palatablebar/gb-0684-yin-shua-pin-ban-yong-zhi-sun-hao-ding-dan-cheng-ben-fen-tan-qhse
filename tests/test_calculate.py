from decimal import Decimal
from app.workflow import run
from app.modules.m5_calculate.rules import apportion,apply

def test_real_stock_conservation(raw):
    s=run(raw,{});assert s['business']['sheets']==4392 and s['business']['leftover']==1608
def test_real_weight_formula(raw):assert Decimal(run(raw,{})['calculations'][0]['weight_kg'])==Decimal('6.832')
def test_real_cost_conservation(raw):
    s=run(raw,{});assert sum(Decimal(r['cost']) for r in s['calculations'])==Decimal(s['business']['total'])==Decimal('1672.47')
def test_largest_remainder():
    # TRAP-24
    assert apportion(['.3333']*3)==[Decimal('.34'),Decimal('.33'),Decimal('.33')]
def test_naive_rounding_counterexample():
    s=apportion(['46.4576']*12);assert sum(s)==Decimal('557.49') and Decimal('46.46')*12==Decimal('557.52')
def test_shortage_never_negative(raw):
    s=run(raw,{},4)
    for d in s['demands']:d['source']['stock']='100'
    r=apply(s);assert all(x['code']=='SHORTAGE' and x['closing']==100 for x in r['calculations']) and r['business']['total']=='0'
def test_deterministic_due_order(raw):
    s=run(raw,{},4);a=apply(s);s=run(raw,{},4);s['demands'].reverse();b=apply(s);assert [(x['id'],x['cost']) for x in a['calculations']]==[(x['id'],x['cost']) for x in b['calculations']]


def test_equivalent_decimal_stock_contracts(raw):
    s=run(raw,{},4);s['demands'][0]['source']['gsm']='80.0';s['demands'][0]['source']['price_kg']='6.800';assert apply(s)['business']['total']=='1672.47'
