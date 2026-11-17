from app.workflow import run
from app.modules.m4_segments.rules import losses

def test_real_net(raw):assert run(raw,{},4)['demands'][0]['net']==100
def test_real_separate_losses(raw):
    d=run(raw,{},4)['demands'][0];assert d['fixed']==20 and d['variable']==2 and d['gross']==122
def test_partial_sheet_roundup():assert losses(1001,10,20,2)['net']==101
def test_variable_roundup():assert losses(1001,10,20,2)['variable']==3
def test_zero_percent_keeps_startup():assert losses(1000,10,20,0)['gross']==120
def test_overprint_not_negative():assert losses(1001,10,20,2)['overprint']==9
def test_real_paper_demand(raw):assert sum(d['gross'] for d in run(raw,{},4)['demands'])==4392
