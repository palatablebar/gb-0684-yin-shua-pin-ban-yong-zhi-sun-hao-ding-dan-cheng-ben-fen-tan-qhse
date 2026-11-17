from decimal import Decimal,ROUND_FLOOR
from collections import defaultdict
from app.errors import DomainError

def layout(paper_w,paper_h,piece_w,piece_h,bleed=0,gap=0,grain='any'):
    sw,sh,pw,ph,b,g=map(lambda v:Decimal(str(v)),(paper_w,paper_h,piece_w,piece_h,bleed,gap))
    if min(sw,sh,pw,ph)<=0 or b<0 or g<0 or grain not in ('any','fixed'):raise DomainError('RANGE','纸张或成品尺寸无效')
    out=[]
    for rotated in (False,True):
        if rotated and grain=='fixed':continue
        w,h=(ph+2*b,pw+2*b) if rotated else (pw+2*b,ph+2*b)
        cols=int(((sw+g)/(w+g)).to_integral_value(rounding=ROUND_FLOOR));rows=int(((sh+g)/(h+g)).to_integral_value(rounding=ROUND_FLOOR))
        out.append({'rotated':rotated,'columns':cols,'rows':rows,'copies':cols*rows,'piece_w':str(w),'piece_h':str(h)})
    best=dict(max(out,key=lambda r:(r['copies'],not r['rotated'])))
    if best['copies']==0:raise DomainError('RANGE','成品无法排入纸张')
    best['alternatives']=out;return best

def apply(state):
    layouts=[];bad=[];groups=defaultdict(list);chosen=[]
    for r in state['rows']:groups[r['order_id']].append(r)
    semantic=('lot','paper_w','paper_h','piece_w','piece_h','bleed','gap','dimension_unit','grain','quantity','gsm','price_kg','fixed_loss','loss_pct','stock','due')
    for order,records in groups.items():
        version=max(Decimal(str(r['version'])) for r in records);latest=[r for r in records if Decimal(str(r['version']))==version]
        signatures={tuple(str(r[k]) for k in semantic) for r in latest}
        if len(signatures)>1:bad.extend((r,'CONFLICT') for r in records)
        else:chosen.append(sorted(latest,key=lambda r:r['id'])[0])
    for r in chosen:
        try:
            factor={'mm':Decimal(1),'cm':Decimal(10)}.get(r['dimension_unit'])
            if factor is None:raise DomainError('UNIT','尺寸单位无效')
            dims={k:Decimal(str(r[k]))*factor for k in ('paper_w','paper_h','piece_w','piece_h','bleed','gap')}
            if any(Decimal(str(r[k]))<0 for k in ('quantity','gsm','price_kg','fixed_loss','loss_pct','stock')) or Decimal(str(r['quantity']))<=0 or Decimal(str(r['gsm']))<=0 or Decimal(str(r['loss_pct']))>100:raise DomainError('RANGE','印量或损耗参数无效')
            if any(Decimal(str(r[k]))!=Decimal(str(r[k])).to_integral_value() for k in ('quantity','fixed_loss','stock')):raise DomainError('RANGE','张数必须为整数')
            choice=layout(**dims,grain=r['grain']);layouts.append({'id':r['order_id'],'record_id':r['id'],'line':r['_line'],'lot':r['lot'],'due':r['due'],'dims':{k:str(v) for k,v in dims.items()},'choice':choice,'source':r})
        except DomainError as e:bad.append((r,e.code))
    lines={r['_line'] for r,_ in bad};state['rows']=[r for r in state['rows'] if r['_line'] not in lines]
    for r,c in bad:state['quarantine'].append({'line':r['_line'],'id':r['id'],'code':c,'raw':r['_raw']})
    state['layouts']=layouts;return state
