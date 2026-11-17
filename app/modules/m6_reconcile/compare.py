from decimal import Decimal

def balance(state):
    accepted=len(state['rows']);isolated=len(state['quarantine']);accounted=accepted+isolated+state['blank_count']+state['header_count']+state['duplicate_count']
    cost=sum((Decimal(r['cost']) for r in state['calculations']),Decimal(0));target=Decimal(state['business']['total'])
    stock_ok=all(l['opening']==l['consumed']+l['closing'] for l in state['lots'])
    return {'input':state['input_count'],'accepted':accepted,'isolated':isolated,'blank':state['blank_count'],'headers':state['header_count'],'duplicates':state['duplicate_count'],'accounted':accounted,'balanced':accounted==state['input_count'] and cost==target and stock_ok,'cost_balanced':cost==target,'stock_balanced':stock_ok,'business':state['business']}
