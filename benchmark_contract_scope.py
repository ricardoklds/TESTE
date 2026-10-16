"""Comparação reproduzível, em bases temporárias: 500 mil Leituras e 100 mil Vistorias."""
import argparse,hashlib,json,os,resource,shutil,subprocess,sys,tempfile,zipfile
from io import BytesIO
from pathlib import Path
from time import perf_counter
BASELINE='568bc75'

def worker(source,data,output):
 sys.path.insert(0,str(Path(source).resolve()));os.environ['APP_DATA_DIR']=str(data)
 import inspection_billing as b,inspections as op
 from streamlit.testing.v1 import AppTest
 from datetime import date
 root=Path(data)/'vistorias';t=perf_counter();b.sync(root);r={'projection_with_backup_seconds':perf_counter()-t,'summary_seconds':[]}
 for _ in range(3):
  t=perf_counter();p=b.preview(root,'2026-09');r['summary_seconds'].append(perf_counter()-t)
 r['inspection_cents']=p['inspection_cents'];r['services']=p['services'];r['pending']=p['pending']
 t=perf_counter();b.detail_page(root,'2026-09',offset=50000);r['page_50000_seconds']=perf_counter()-t
 t=perf_counter();total,_,_=op.summary(root,'2026-09-01','2026-09-30');r['deadline_seconds']=perf_counter()-t;r['operational_total']=total['total']
 a=AppTest.from_file(str(Path(source)/'app.py'),default_timeout=180).run();assert not a.exception
 a.sidebar.date_input[0].set_value(date(2026,9,1)).run();assert not a.exception;r['readings_total']=a.metric[0].value;r['holiday_value']=a.metric[2].value
 r['readings_cached_seconds']=[]
 for _ in range(3):
  t=perf_counter();a.run();r['readings_cached_seconds'].append(perf_counter()-t);assert not a.exception
 t=perf_counter();a.sidebar.selectbox[0].set_value('Vistorias').run();r['visits_first_navigation_seconds']=perf_counter()-t;assert not a.exception
 t=perf_counter();a.run();r['visits_cached_seconds']=perf_counter()-t;assert not a.exception
 t=perf_counter();a.sidebar.radio[0].set_value('Prazos e Meta Contratual').run();r['deadline_navigation_seconds']=perf_counter()-t;assert not a.exception
 t=perf_counter();a.sidebar.selectbox[0].set_value('Leituras').run();r['return_readings_seconds']=perf_counter()-t;assert not a.exception
 t=perf_counter();report=b.reconciliation(root,'2026-09',detail=False);r['summary_excel_seconds']=perf_counter()-t;r['summary_excel_bytes']=len(report)
 r['peak_rss_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
 Path(output).write_text(json.dumps(r,indent=2))

def run(output,reading_rows=500000,visit_rows=100000):
 from benchmark_independent_compare import fixture
 import inspections
 output=Path(output);output.mkdir(parents=True,exist_ok=False)
 with tempfile.TemporaryDirectory(prefix='scope-benchmark-') as tmp:
  tmp=Path(tmp);data,_,_,ref=fixture(tmp,reading_rows);bank=data/'contrato.sqlite3';original_hash=hashlib.sha256(bank.read_bytes()).hexdigest();root=data/'vistorias'
  with inspections.connect(root) as c:
   c.execute("INSERT INTO imports VALUES(1,'synthetic','Número OS','synthetic.xlsx','2026-09-01')")
   for start in range(0,visit_rows,2000):
    batch=[]
    for i in range(start,min(start+2000,visit_rows)):
     city='BOCAINA' if i%2 else 'AGUDOS';late=i%100==0
     raw={'Número OS':str(i),'TSS':'VISTORIA DE NOVA LIGAÇÃO DE ÁGUA' if i%2 else 'VISTORIA CADASTRAL','Contrato':'SINTETICO','Município':city,'Status da OS':'Fechada','Status da Operação':'Fechada','Data Fim Execução':'02/09/2026 10:01' if late else '02/09/2026 10:00','Prazo de Execução - Fim':'02/09/2026 10:00'}
     batch.append((1,i+2,str(i),city,'2026-09-02','Fora do prazo' if late else 'Dentro do prazo',str(i),json.dumps(raw,ensure_ascii=False)))
    c.executemany('INSERT INTO visits(import_id,line,os,city,day,status,fingerprint,raw) VALUES(?,?,?,?,?,?,?,?)',batch)
  old=tmp/'old';old.mkdir()
  with zipfile.ZipFile(BytesIO(subprocess.check_output(['git','archive','--format=zip',BASELINE]))) as z:z.extractall(old)
  results={}
  for variant,source in [('before',old),('after',Path(__file__).resolve().parent)]:
   isolated=tmp/variant;shutil.copytree(data,isolated);target=output/(variant+'.json')
   with (output/(variant+'-log.txt')).open('w') as log:subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker','--source',str(source),'--data',str(isolated),'--output',str(target)],check=True,stdout=log,stderr=subprocess.STDOUT)
   results[variant]=json.loads(target.read_text());assert hashlib.sha256((isolated/'contrato.sqlite3').read_bytes()).hexdigest()==original_hash
  for key in ['inspection_cents','services','pending','operational_total','readings_total','holiday_value']:assert results['before'][key]==results['after'][key],key
  assert results['after']['inspection_cents']==((visit_rows+1)//2)*1200+(visit_rows//2)*2250
  import contract_finance
  readings=contract_finance.readings(data,'2026-09');assert readings['cents']==ref['independent_total_cents'];assert readings['units']==ref['independent_quantities'];assert hashlib.sha256(bank.read_bytes()).hexdigest()==original_hash
  report={'baseline':BASELINE,'synthetic':True,'reading_rows':reading_rows,'visit_rows':visit_rows,**results,'six_reading_quantities_identical':True,'readings_bank_unchanged':True,'production_accessed':False,'limits':'Dados sintéticos SQL, não Excel. AppTest mede execução no servidor, não navegador/rede. RAM é pico de cada processo completo, incluindo Streamlit. Vistorias sintéticas únicas, autorizadas e com datas válidas; divergências comerciais de OS repetidas e municípios cobertas por testes separados.'}
  (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--worker',action='store_true');p.add_argument('--source');p.add_argument('--data');p.add_argument('--readings',type=int,default=500000);p.add_argument('--visits',type=int,default=100000);a=p.parse_args()
 if a.worker:worker(a.source,a.data,a.output)
 else:run(a.output,a.readings,a.visits)
