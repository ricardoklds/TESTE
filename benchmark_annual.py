"""Benchmark anual reproduzível, exclusivamente com SQL sintético e bases temporárias."""
import argparse,hashlib,json,os,subprocess,sys,tempfile,zipfile,shutil,time
from io import BytesIO
from pathlib import Path

BASELINE='bd0e97b'
def worker(source,data,output,annual):
 sys.path.insert(0,str(source));os.environ['APP_DATA_DIR']=str(data)
 from streamlit.testing.v1 import AppTest
 from contract_finance import state
 def hashes():return {str(p.relative_to(data)):hashlib.sha256(p.read_bytes()).hexdigest() for p in data.rglob('*.sqlite3')}
 before=hashes();result={};a=AppTest.from_file(str(source/'app.py'),default_timeout=180).run();assert not a.exception
 def click(key):
  next(b for b in a.sidebar.button if b.key==key).click().run();assert not a.exception
 a.sidebar.selectbox(key='reference_month').set_value(9).run();assert not a.exception
 click('nav:Fechamento geral:Consolidação financeira mensal');result['closing_cached_s']=[]
 for _ in range(5):
  t=time.perf_counter();a.run();result['closing_cached_s'].append(time.perf_counter()-t);assert not a.exception
 result['official']=state(data,'2026-09')
 if annual:
  t=time.perf_counter();click('nav:Faturamento Anual:Faturamento Anual');result['annual_cold_s']=time.perf_counter()-t
  result['annual_cached_s']=[]
  for _ in range(5):
   t=time.perf_counter();a.run();result['annual_cached_s'].append(time.perf_counter()-t);assert not a.exception
  import annual_billing as api,annual_reports as reports
  r=api.analyze(api.monthly(data,'2025-02','2026-12'),2026,12)
  assert next(x for x in r['rows'] if x['month']=='2026-09')['gross_cents']==result['official']['gross_cents']
  for key,export in [('pdf',reports.pdf),('excel',reports.excel)]:
   t=time.perf_counter();blob=export(r);result[key+'_s']=time.perf_counter()-t;result[key+'_bytes']=len(blob)
 result['banks_unchanged']=hashes()==before;assert result['banks_unchanged']
 Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2))

def run(output,n=400000,vn=100000):
 from benchmark_independent_compare import fixture
 import inspections,inspection_billing as bill,contract_finance as contract
 output=Path(output);output.mkdir(parents=True,exist_ok=False)
 with tempfile.TemporaryDirectory(prefix='annual-benchmark-') as temp:
  temp=Path(temp);data,_,_,_=fixture(temp,n);root=data/'vistorias'
  with inspections.connect(root) as c:
   c.execute("INSERT INTO imports VALUES(1,'synthetic','Número OS','synthetic.xlsx','2026-09-01')")
   for start in range(0,vn,2000):
    batch=[]
    for i in range(start,min(start+2000,vn)):
     raw={'Número OS':str(i),'TSS':'VISTORIA CADASTRAL','Contrato':'SINTETICO','Município':'BOCAINA','Status da OS':'Fechada','Status da Operação':'Fechada','Data Fim Execução':'02/09/2026 10:00','Prazo de Execução - Fim':'02/09/2026 10:00'}
     batch.append((1,i+2,str(i),'BOCAINA','2026-09-02','Dentro do prazo',str(i),json.dumps(raw,ensure_ascii=False)))
    c.executemany('INSERT INTO visits(import_id,line,os,city,day,status,fingerprint,raw) VALUES(?,?,?,?,?,?,?,?)',batch)
  bill.sync(root);bill.save_geo(root,'2026-09','Total mensal',10,{})
  snapshot=contract.preview(data,'2026-09')
  # Fotografias fabricadas SOMENTE para medir histórico aprovado; não são fechamentos reais.
  with contract.connect(data) as c:
   for year,first in [(2025,2),(2026,1)]:
    for m in range(first,13):
     month=f'{year}-{m:02d}'
     if month=='2026-09':continue
     p={**snapshot,'month':month};c.execute('INSERT INTO closings VALUES(?,?,?,?)',(month,json.dumps(p),'synthetic','synthetic'))
  old=temp/'baseline';old.mkdir()
  with zipfile.ZipFile(BytesIO(subprocess.check_output(['git','archive','--format=zip',BASELINE]))) as z:z.extractall(old)
  results={'synthetic':True,'production_accessed':False,'reading_rows':n,'visit_rows':vn,'approved_synthetic_snapshots':22,'open_months':1,'baseline':BASELINE}
  for label,source in [('before',old),('after',Path(__file__).resolve().parent)]:
   isolated=temp/label;shutil.copytree(data,isolated)
   with (output/(label+'.log')).open('w') as log:subprocess.run([sys.executable,__file__,'--worker','--source',str(source),'--data',str(isolated),'--output',str(output/(label+'.json')),*(['--annual'] if label=='after' else [])],check=True,stdout=log,stderr=subprocess.STDOUT)
   results[label]=json.loads((output/(label+'.json')).read_text())
  a=results['before']['official'];b=results['after']['official']
  assert a==b;results['financial_state_identical']=True
  results['limits']='AppTest mede servidor Python; não navegador/rede. Um mês aberto com 400 mil leituras e 100 mil vistorias, 22 fotografias aprovadas sintéticas. Não mede vários meses abertos simultâneos ou importação Excel.'
  (output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in results.items() if k not in ('before','after')},ensure_ascii=False))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker',action='store_true');p.add_argument('--annual',action='store_true');p.add_argument('--source');p.add_argument('--data');p.add_argument('--output',required=True);a=p.parse_args()
 if a.worker:worker(Path(a.source),Path(a.data),a.output,a.annual)
 else:run(a.output)
