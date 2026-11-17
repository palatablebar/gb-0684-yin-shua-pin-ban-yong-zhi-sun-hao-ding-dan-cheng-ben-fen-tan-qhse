from decimal import Decimal,ROUND_DOWN,ROUND_HALF_UP
from collections import defaultdict
from app.errors import DomainError

def apportion(values):
    values=[Decimal(str(v)) for v in values];target=sum(values,Decimal(0)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    allocated=[v.quantize(Decimal('.01'),rounding=ROUND_DOWN) for v in values];pennies=int((target-sum(allocated))/Decimal('.01'))
    for i in sorted(range(len(values)),key=lambda i:(-(values[i]-allocated[i]),i))[:pennies]:allocated[i]+=Decimal('.01')
    return allocated

def apply(state):
    grouped=defaultdict(list)
    for d in state['demands']:grouped[d['lot']].append(d)
    calculations=[];lots=[]
    for lot,orders in sorted(grouped.items()):
        contracts={tuple(Decimal(str(v)) for v in (o['source']['stock'],o['source']['gsm'],o['source']['price_kg'],o['dims']['paper_w'],o['dims']['paper_h'])) for o in orders}
        if len(contracts)!=1:raise DomainError('CONFLICT','同纸批库存或材质定义冲突')
        stock=int(Decimal(str(orders[0]['source']['stock'])));opening=stock;ready=[];exact=[]
        for d in sorted(orders,key=lambda o:(o['due'],o['id'])):
            r=d['source'];amount=d['gross'];weight=Decimal(amount)*Decimal(d['dims']['paper_w'])*Decimal(d['dims']['paper_h'])/1000000*Decimal(str(r['gsm']))/1000
            enough=amount<=stock;closing=stock-amount if enough else stock
            item={'id':d['id'],'line':d['line'],'lot':lot,'copies':d['choice']['copies'],'rotated':d['choice']['rotated'],'net':d['net'],'fixed_loss':d['fixed'],'run_loss':d['variable'],'gross':amount,'opening':stock,'closing':closing,'shortage':max(0,amount-stock),'weight_kg':str(weight),'cost':'0.00','code':'RELEASED' if enough else 'SHORTAGE'}
            calculations.append(item)
            if enough:ready.append(item);exact.append(weight*Decimal(str(r['price_kg'])));stock=closing
        allocated=apportion(exact)
        for item,cost in zip(ready,allocated):item['cost']=str(cost)
        lots.append({'id':lot,'opening':opening,'closing':stock,'consumed':opening-stock,'cost':str(sum(allocated,Decimal(0)))})
    state['calculations']=calculations;state['lots']=lots;state['business']={'total':str(sum((Decimal(l['cost']) for l in lots),Decimal(0))),'sheets':sum(l['consumed'] for l in lots),'leftover':sum(l['closing'] for l in lots),'shortage_orders':sum(r['code']=='SHORTAGE' for r in calculations),'unit':'CNY'};return state
