"""Antes/depois isolado: 500 mil Leituras e 100 mil Vistorias. Nunca abre produção."""
import argparse,json,os,sys,subprocess,tempfile,zipfile
from pathlib import Path
from io import BytesIO
from time import perf_counter

def worker(source,data,out,variant):
    sys.path.insert(0,str(Path(source).resolve()));os.environ['APP_DATA_DIR']=str(data)
    from streamlit.testing.v1 import AppTest
    from datetime import date
    import managerial,storage
    at=AppTest.from_file(str(Path(source)/'app.py'),default_timeout=180).run();assert not at.exception
    t=perf_counter();at.sidebar.date_input[0].set_value(date(2026,9,1)).run();cold=perf_counter()-t;assert not at.exception
    result={'readings_panel_month_first_seconds':cold,'readings_panel_cached_seconds':[],'readings_total':at.metric[0].value,'holiday_value':at.metric[2].value}
    for _ in range(3):
        t=perf_counter();at.run();result['readings_panel_cached_seconds'].append(perf_counter()-t);assert not at.exception
    import inspections
    t=perf_counter();total,_,pending=inspections.summary(Path(data)/'vistorias','2026-09-01','2026-09-30');result['deadline_aggregate_seconds']=perf_counter()-t;result['operational_total']=total
    t=perf_counter()
    if variant=='before':at.sidebar.radio[0].set_value('Vistorias').run()
    else:
        at.sidebar.selectbox[0].set_value('Vistorias').run();result['inspection_module_entry_financial_panel_seconds']=perf_counter()-t
        t=perf_counter();at.sidebar.radio[0].set_value('Prazos e Meta Contratual').run()
    result['deadline_navigation_seconds']=perf_counter()-t;assert not at.exception
    if variant=='after':
        import inspection_billing as b
        t=perf_counter();p=b.preview(Path(data)/'vistorias','2026-09');result['inspection_financial_aggregate_seconds']=perf_counter()-t;result['inspection_cents']=p['inspection_cents'];result['inspection_pending']=p['pending']
        t=perf_counter();at.sidebar.radio[0].set_value('Painel de Vistorias').run();result['inspection_financial_panel_revisit_seconds']=perf_counter()-t;assert not at.exception
        t=perf_counter();at.run();result['inspection_financial_panel_cached_seconds']=perf_counter()-t;assert not at.exception
        t=perf_counter();at.sidebar.selectbox[0].set_value('Painel geral').run();result['general_panel_first_seconds']=perf_counter()-t;assert not at.exception
        t=perf_counter();at.run();result['general_panel_cached_seconds']=perf_counter()-t;assert not at.exception
    Path(out).write_text(json.dumps(result,ensure_ascii=False,indent=2))

def run(output,reading_rows=500000,visit_rows=100000):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    from benchmark_independent_compare import fixture
    import inspections,inspection_billing as bill
    from validacao_independente import sha
    with tempfile.TemporaryDirectory(prefix='modular-sabesp-benchmark-') as tmp:
        temp=Path(tmp);data,_,_,ref=fixture(temp,reading_rows);bank_before=sha(data/'contrato.sqlite3');root=data/'vistorias'
        with inspections.connect(root) as c:
            c.execute("INSERT INTO imports VALUES(1,'synthetic','Número OS','sintetico.xlsx','2026-09-01')")
            for start in range(0,visit_rows,2000):
                batch=[]
                for i in range(start,min(start+2000,visit_rows)):
                    late=i%100==0;raw={'Número OS':str(i),'TSS':'VISTORIA CADASTRAL','Contrato':'TESTE','Família':'VISTORIA','Causa Resultado':'EXECUTADA','Formulário de Baixa':'TESTE','Status da OS':'Fechada','Status da Operação':'Fechada','Prazo de Execução - Fim':'02/09/2026 10:00','Data Fim Execução':'02/09/2026 10:01' if late else '02/09/2026 10:00'}
                    batch.append((1,i+2,str(i),'Cidade '+str(i%100),'2026-09-02','Fora do prazo' if late else 'Dentro do prazo',str(i),json.dumps(raw,ensure_ascii=False)))
                c.executemany('INSERT INTO visits(import_id,line,os,city,day,status,fingerprint,raw) VALUES(?,?,?,?,?,?,?,?)',batch)
        t=perf_counter();bill.sync(root);sync_seconds=perf_counter()-t
        old=temp/'before';old.mkdir()
        with zipfile.ZipFile(BytesIO(subprocess.check_output(['git','archive','--format=zip','608c111']))) as z:z.extractall(old)
        results={}
        for variant,source in [('before',old),('after',Path(__file__).resolve().parent)]:
            target=output/(variant+'.json')
            with (output/(variant+'-log.txt')).open('w') as log:subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker','--source',str(source),'--data',str(data),'--output',str(target),'--variant',variant],check=True,stdout=log,stderr=subprocess.STDOUT)
            results[variant]=json.loads(target.read_text())
        assert results['before']['readings_total']==results['after']['readings_total']
        assert results['before']['holiday_value']==results['after']['holiday_value']
        assert results['before']['operational_total']==results['after']['operational_total']
        assert results['after']['inspection_cents']==visit_rows*1200
        assert sha(data/'contrato.sqlite3')==bank_before
        import contract_finance as contract
        total=contract.readings(data,'2026-09');assert total['cents']==ref['independent_total_cents'];assert total['units']==ref['independent_quantities']
        report={'synthetic':True,'reading_rows':reading_rows,'visit_rows':visit_rows,'sync_with_initial_backup_seconds':sync_seconds,**results,'six_reading_quantities_identical':True,'readings_bank_sha256_unchanged':True,'production_accessed':False,'limits':'SQL fixtures. AppTest mede servidor, não navegador/rede. Três amostras cacheadas de Leituras. Prazo mede a seleção da página; a entrada no módulo financeiro é medida separadamente após a mudança. Não é ensaio de importação Excel de 500 mil registros nem validação real de setembro.'}
        (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--worker',action='store_true');p.add_argument('--source');p.add_argument('--data');p.add_argument('--variant');p.add_argument('--output',required=True);p.add_argument('--readings',type=int,default=500000);p.add_argument('--visits',type=int,default=100000);a=p.parse_args()
    if a.worker:worker(a.source,Path(a.data),a.output,a.variant)
    else:run(a.output,a.readings,a.visits)
