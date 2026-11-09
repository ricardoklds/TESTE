"""Mede catálogo com 100 mil vistorias sintéticas, comparando o commit anterior."""
import argparse,json,subprocess,sys,tempfile,zipfile,hashlib
from pathlib import Path
from time import perf_counter
from io import BytesIO

def worker(source,root,out,variant):
 sys.path.insert(0,str(Path(source).resolve()));import inspection_billing as b
 rows=[]
 for _ in range(3):
  t=perf_counter();p=b.preview(root,'2026-09');rows.append(perf_counter()-t)
 r={'variant':variant,'summary_seconds':rows,'inspection_cents':p['inspection_cents'],'quantity':sum(s['quantity'] for s in p['services'])}
 if variant=='after':
  bank=Path(root)/'financeiro.sqlite3';before=hashlib.sha256(bank.read_bytes()).hexdigest()
  t=perf_counter();plan=b.prepare_change(root,{'kind':'rule','tss':'VISTORIA CADASTRAL','cause':'','form':'','effective':'2026-09','decision':'Cobrar','code':'200014106','unit_cents':None,'evidence':'Teste sintético de impacto'});r['impact_preview_seconds']=perf_counter()-t
  r['impact_delta_cents']=plan['impact'][0]['delta_cents'];r['simulation_bank_unchanged']=before==hashlib.sha256(bank.read_bytes()).hexdigest();assert r['simulation_bank_unchanged']
 Path(out).write_text(json.dumps(r,indent=2))

def run(output,n=100000):
 import inspections,inspection_billing as b
 output=Path(output);output.mkdir(parents=True,exist_ok=False)
 with tempfile.TemporaryDirectory(prefix='catalog-bench-') as tmp:
  tmp=Path(tmp);root=tmp/'vistorias'
  with inspections.connect(root) as c:
   c.execute("INSERT INTO imports VALUES(1,'synthetic','Número OS','synthetic.xlsx','2026-09-01')")
   for start in range(0,n,2000):
    values=[]
    for i in range(start,min(n,start+2000)):
     raw=json.dumps({'TSS':'VISTORIA CADASTRAL','Contrato':'TESTE','Status da OS':'Fechada','Status da Operação':'Fechada'})
     values.append((1,i+2,str(i),'Cidade '+str(i%100),'2026-09-01','Dentro do prazo',str(i),raw))
    c.executemany('INSERT INTO visits(import_id,line,os,city,day,status,fingerprint,raw) VALUES(?,?,?,?,?,?,?,?)',values)
  b.sync(root);old=tmp/'before';old.mkdir()
  with zipfile.ZipFile(BytesIO(subprocess.check_output(['git','archive','--format=zip','57c8290']))) as z:z.extractall(old)
  result={'synthetic':True,'rows':n,'baseline':'57c8290','production_accessed':False}
  for variant,source in [('before',old),('after',Path(__file__).resolve().parent)]:
   target=output/(variant+'.json');subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker','--source',str(source),'--root',str(root),'--output',str(target),'--variant',variant],check=True);result[variant]=json.loads(target.read_text())
  assert result['before']['inspection_cents']==result['after']['inspection_cents'];assert result['after']['quantity']==n
  (output/'results.json').write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',required=True);p.add_argument('--worker',action='store_true');p.add_argument('--root');p.add_argument('--source');p.add_argument('--variant');a=p.parse_args()
 if a.worker:worker(a.source,a.root,a.output,a.variant)
 else:run(a.output)
