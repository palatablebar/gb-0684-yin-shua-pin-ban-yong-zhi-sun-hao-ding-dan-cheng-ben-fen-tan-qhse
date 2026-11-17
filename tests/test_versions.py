import pytest
from app.workflow import run
from app.modules.m3_versions.rules import layout,apply
from app.errors import DomainError

def test_real_rotation_selected(raw):
    c=run(raw,{},3)['layouts'][0]['choice'];assert c['copies']==10 and c['rotated'] is True
def test_uniform_unrotated_counterexample():
    c=layout(1000,700,300,200);assert [x['copies'] for x in c['alternatives']]==[9,10]
def test_grain_blocks_rotation():assert layout(1000,700,300,200,grain='fixed')['copies']==9
def test_real_cm_conversion(raw):
    # TRAP-15: cm尺寸须乘10统一为mm，排版结果与等尺寸mm输入一致。
    s=run(raw,{},2);r=s['rows'][0];r.update(paper_w='100',paper_h='70',piece_w='30',piece_h='20',dimension_unit='cm');result=apply(s)['layouts'][0]
    assert result['dims']=={'paper_w':'1000','paper_h':'700','piece_w':'300','piece_h':'200','bleed':'0','gap':'0'}
    assert result['choice']['copies']==10 and result['choice']['rotated'] is True
def test_real_bleed_reduces_fit(raw):
    s=run(raw,{},2);s['rows'][0]['bleed']='5';assert apply(s)['layouts'][0]['choice']['copies']<10
def test_impossible_piece():
    with pytest.raises(DomainError):layout(100,100,200,200)
def test_real_order_count(raw):assert len(run(raw,{},3)['layouts'])==36


def test_order_revision_only_latest_computed(raw):
    s=run(raw,{},2);new=dict(s['rows'][0],id='revision',version='2',quantity='2000',_line=999);s['rows'].append(new);r=apply(s)
    chosen=[x for x in r['layouts'] if x['id']=='PO0001'];assert len(chosen)==1 and str(chosen[0]['source']['quantity'])=='2000'

def test_order_same_version_conflict_isolated(raw):
    s=run(raw,{},2);new=dict(s['rows'][0],id='conflict',quantity='2000',_line=999);s['rows'].append(new);r=apply(s)
    assert all(x['id']!='PO0001' for x in r['layouts']) and sum(q['code']=='CONFLICT' for q in r['quarantine'])==4
