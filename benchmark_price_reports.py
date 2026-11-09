"""Mede composição e relatórios sob demanda em bases sintéticas isoladas."""
import argparse,hashlib,json,os,resource,shutil,subprocess,sys,tempfile,zipfile
from io import BytesIO
from pathlib import Path
from time import perf_counter
BASELINE='5ba82eb'

def worker(source,data,output,variant):
 sys.path.insert(0,str(Path(source).resolve()));os.environ['APP_DATA_DIR']=str(data)
 from streamlit.testing.v1 import AppTest
 from datetime import date
 import contract_finance as c,inspection_billing as b
 def hashes():return {str(p.relative_to(data)):hashlib.sha256(p.read_bytes()).hexdigest() for p in data.rglob('*.sqlite3')}
 def go(a,module,page=None):
  first={'Leituras':'Painel inicial','Vistorias':'Painel de Vistorias','Fechamento geral':'Consolidação financeira mensal'}
  next(v for v in a.sidebar.button if v.key=='nav:'+module+':'+(page or first[module])).click().run()
  assert not a.exception
 a=AppTest.from_file(str(Path(source)/'app.py'),default_timeout=180).run();a.sidebar.date_input[0].set_value(date(2026,9,1)).run();assert not a.exception
 result={'readings_cached_seconds':[],'closing_cached_seconds':[],'simulation_seconds':[]}
 result['readings_total']=a.metric[0].value;result['holiday_total']=a.metric[2].value
 for _ in range(3):
  t=perf_counter();a.run();result['readings_cached_seconds'].append(perf_counter()-t);assert not a.exception
 t=perf_counter();go(a,'Vistorias');result['visits_first_navigation_seconds']=perf_counter()-t
 t=perf_counter();go(a,'Leituras');result['return_readings_seconds']=perf_counter()-t
 t=perf_counter();go(a,'Fechamento geral');result['closing_first_seconds']=perf_counter()-t
 import contract_ui
 result['closing_uncached_seconds']=[]
 for _ in range(3):
  contract_ui.cached_state.clear();t=perf_counter();a.run();result['closing_uncached_seconds'].append(perf_counter()-t);assert not a.exception
 for _ in range(3):
  t=perf_counter();a.run();result['closing_cached_seconds'].append(perf_counter()-t);assert not a.exception
 before=hashes()
 for enabled in [True,False,True,False]:
  t=perf_counter();a.toggle[0].set_value(enabled).run();result['simulation_seconds'].append(perf_counter()-t);assert not a.exception
 if variant=='after':
  from contract_presentation import compose
  import contract_reports
  presentation=compose(data,c.state(data,'2026-09'))
  t=perf_counter();blob=contract_reports.pdf(presentation,False);result['pdf_seconds']=perf_counter()-t;result['pdf_bytes']=len(blob)
  t=perf_counter();blob=contract_reports.excel(presentation,False);result['excel_seconds']=perf_counter()-t;result['excel_bytes']=len(blob)
  t=perf_counter();next(v for v in a.button if v.label=='Gerar relatório de prévia').click().run();result['ui_both_exports_seconds']=perf_counter()-t;assert not a.exception
  result['composition_rows']=len(presentation['rows']);result['composition_total_equals_gross']=sum(r['cents'] for r in presentation['rows'])==presentation['gross_cents'];assert result['composition_total_equals_gross']
 result['simulation_banks_unchanged']=before==hashes();assert result['simulation_banks_unchanged']
 result['before_geo']=c.preview(data,'2026-09')
 t=perf_counter();go(a,'Vistorias','Geolocalização');result['geo_entry_seconds']=perf_counter()-t
 next(v for v in a.number_input if v.label=='Quantidade').set_value(7).run();button=next(v for v in a.button if v.label=='Salvar')
 t=perf_counter();button.click().run();result['geo_save_seconds']=perf_counter()-t;assert not a.exception
 result['after_geo']=c.preview(data,'2026-09');assert result['after_geo']['visits']['geo']['cents']==8400
 result['peak_rss_mib']=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
 Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2))

def run(output,reading_rows=500000,visit_rows=100000):
 from benchmark_independent_compare import fixture
 import inspections,inspection_billing as b,contract_finance
 output=Path(output);output.mkdir(parents=True,exist_ok=False)
 with tempfile.TemporaryDirectory(prefix='price-reports-benchmark-') as tmp:
  tmp=Path(tmp);data,_,_,reference=fixture(tmp,reading_rows);root=data/'vistorias'
  with inspections.connect(root) as c:
   c.execute("INSERT INTO imports VALUES(1,'synthetic','Número OS','synthetic.xlsx','2026-09-01')")
   for start in range(0,visit_rows,2000):
    batch=[]
    for i in range(start,min(start+2000,visit_rows)):
     raw={'Número OS':str(i),'TSS':'VISTORIA CADASTRAL' if i%2 else 'VISTORIA DE NOVA LIGAÇÃO DE ÁGUA','Contrato':'SINTETICO','Município':'BOCAINA','Status da OS':'Fechada','Status da Operação':'Fechada','Data Fim Execução':'02/09/2026 10:00','Prazo de Execução - Fim':'02/09/2026 10:00'}
     batch.append((1,i+2,str(i),'BOCAINA','2026-09-02','Dentro do prazo',str(i),json.dumps(raw,ensure_ascii=False)))
    c.executemany('INSERT INTO visits(import_id,line,os,city,day,status,fingerprint,raw) VALUES(?,?,?,?,?,?,?,?)',batch)
  b.sync(root);b.save_geo(root,'2026-09','Total mensal',10,{},'Teste sintético')
  read=contract_finance.readings(data,'2026-09');assert read['cents']==reference['independent_total_cents'];assert read['units']==reference['independent_quantities']
  old=tmp/'code-before';old.mkdir()
  with zipfile.ZipFile(BytesIO(subprocess.check_output(['git','archive','--format=zip',BASELINE]))) as z:z.extractall(old)
  results={'baseline':BASELINE,'synthetic':True,'reading_rows':reading_rows,'visit_rows':visit_rows,'production_accessed':False,'six_reading_quantities_checked':True}
  for variant,source in [('before',old),('after',Path(__file__).resolve().parent)]:
   isolated=tmp/variant;shutil.copytree(data,isolated);target=output/(variant+'.json');bank=isolated/'contrato.sqlite3';sha=hashlib.sha256(bank.read_bytes()).hexdigest()
   with (output/(variant+'-log.txt')).open('w') as log:subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker','--source',str(source),'--data',str(isolated),'--output',str(target),'--variant',variant],check=True,stdout=log,stderr=subprocess.STDOUT)
   results[variant]=json.loads(target.read_text());assert hashlib.sha256(bank.read_bytes()).hexdigest()==sha
  for state in ['before_geo','after_geo']:
   for component in ['readings','visits','gross_cents']:
    if component=='visits':
     for key in ['inspection_cents','services','groups','geo']:assert results['before'][state]['visits'][key]==results['after'][state]['visits'][key],key
    elif component=='readings':
     for key in ['cents','closed','units']:assert results['before'][state][component][key]==results['after'][state][component][key],key
    else:assert results['before'][state][component]==results['after'][state][component],component
  results['readings_bank_unchanged']=True;results['financial_components_identical']=True
  results['limits']='Dados SQL sintéticos. AppTest mede o servidor, não navegador/rede nem importação Excel. A expansão nativa do menu é local no navegador e não é cronometrada pelo AppTest. As duas versões têm simulação; as exportações gerenciais completas só existem na nova versão. Geolocalização é alterada apenas em bancos temporários.'
  (output/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in results.items() if k not in ['before','after']},ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--worker',action='store_true');p.add_argument('--source');p.add_argument('--data');p.add_argument('--variant');p.add_argument('--readings',type=int,default=500000);p.add_argument('--visits',type=int,default=100000);a=p.parse_args()
 if a.worker:worker(a.source,Path(a.data),a.output,a.variant)
 else:run(a.output,a.readings,a.visits)
