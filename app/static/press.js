'use strict';
const press={running:false};const result=document.getElementById('result');
async function rebuild(input){if(press.running)return;press.running=true;result.textContent='正在核算纸耗…';try{const response=await fetch('/api/runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(input)});const data=await response.json();if(!response.ok)throw Error(data.message);location.reload();}catch(error){result.textContent=error.message+'，请核对工单';}finally{press.running=false;}}
document.getElementById('retry').addEventListener('click',()=>rebuild({sample:'dirty.csv'}));document.getElementById('print').addEventListener('click',()=>print());
const input=document.getElementById('job-input');if(input)input.addEventListener('submit',event=>{event.preventDefault();const fields=new FormData(input);const csv=fields.get('csv');rebuild(csv?{csv}:{sample:fields.get('sample')});});
const release=document.getElementById('release');if(release)release.addEventListener('click',async()=>{try{const response=await fetch('/api/runs/'+release.dataset.id+'/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({version:Number(release.dataset.v),decision:'通过'})});const data=await response.json();if(!response.ok)throw Error(data.message);release.dataset.v=data.review_version;result.textContent='已放行 / REV '+data.review_version;}catch(error){result.textContent=error.message;}});
const revisionForm=document.getElementById('revision-input');
if(revisionForm){
  const collect=()=>Object.fromEntries(new FormData(revisionForm).entries());
  revisionForm.addEventListener('submit',async event=>{event.preventDefault();result.textContent='正在预演补差结算…';
    try{const r=await fetch('/api/m8_revision',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(collect())});const d=await r.json();if(!r.ok)throw Error(d.message);
      result.textContent='预演完成：本期差额 '+d.revision_summary.cost_delta+' CNY，重开将改写 '+d.revision_summary.reopen_rewrite_if_chosen+'（仅对比）。点“生成并落库”入账。';
    }catch(e){result.textContent=e.message;}});
  const saveBtn=document.getElementById('revision-save');
  saveBtn.addEventListener('click',async()=>{result.textContent='正在落库修订结算单…';
    try{const r=await fetch('/api/revision_runs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(collect())});const d=await r.json();if(!r.ok)throw Error(d.message);
      result.textContent='结算单已落库 '+d.run_id+'；同修订重跑复用此单，不新增差额。';location.reload();
    }catch(e){result.textContent='结算失败，已回滚旧版：'+e.message;}});
}
