from decimal import Decimal,ROUND_CEILING

def losses(quantity,copies,fixed,percent):
    q=Decimal(str(quantity));p=Decimal(str(percent));f=Decimal(str(fixed))
    net=int((q/Decimal(copies)).to_integral_value(rounding=ROUND_CEILING));variable=int((Decimal(net)*p/100).to_integral_value(rounding=ROUND_CEILING))
    return {'net':net,'fixed':int(f),'variable':variable,'gross':net+int(f)+variable,'capacity':net*copies,'overprint':net*copies-int(q)}

def apply(state):
    demands=[]
    for item in state['layouts']:
        r=item['source'];result=losses(r['quantity'],item['choice']['copies'],r['fixed_loss'],r['loss_pct']);result.update(item);demands.append(result)
    state['demands']=demands;return state
