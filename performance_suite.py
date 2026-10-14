"""Teste reproduzível, sintético e isolado. Nunca abre data/ da instalação.

Executar com --help. Cada medição deve rodar em processo novo, para isolar RAM.
"""
import argparse
import cProfile
from contextlib import contextmanager
from datetime import date, timedelta
import hashlib
import json
import os
import pstats
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import time


def rss():
    # Linux: memória residente efetiva, não memória virtual ou estimativa.
    for line in Path('/proc/self/status').read_text().splitlines():
        if line.startswith('VmRSS:'):
            return int(line.split()[1]) / 1024


@contextmanager
def measure(results, name, sample_memory=True):
    stop = threading.Event(); samples = [rss()]
    def sample():
        while not stop.wait(.02): samples.append(rss())
    worker = threading.Thread(target=sample, daemon=True) if sample_memory else None
    if worker: worker.start()
    begin = time.perf_counter()
    try: yield
    finally:
        samples.append(rss()); stop.set()
        if worker: worker.join()
        results[name] = {'seconds': round(time.perf_counter()-begin, 6),
                         'peak_rss_mb': round(max(samples), 2)}


def fixture(directory):
    import openpyxl, core
    directory.mkdir(parents=True, exist_ok=True)
    headers = list(core.FIELDS.values()) + [f'Campo sintético {i:02}' for i in range(61)]
    manifest = []
    for day_index in range(50):
        day = date(2026, 9, 1) + timedelta(days=day_index)
        path = directory / f'SINTETICO-{day.isoformat()}.xlsx'
        if not path.exists():
            book = openpyxl.Workbook(write_only=True); sheet = book.create_sheet('Leituras')
            sheet.append(headers)
            for row in range(20000):
                index = day_index*20000+row
                sheet.append(['Sim' if index % 2 else 'Não', 'Sim' if index % 13 == 0 else 'Não',
                              '01' if index % 11 == 0 else None, index % 4,
                              '1' if index % 3 == 0 else None, f'TESTE Funcionário {index % 100}',
                              ['ATC AGUDOS','ATC ARACARIGUAMA','RIO DE JANEIRO/RJ','ATC BOM JESUS','LOCAL NÃO IDENTIFICADO'][index % 5],
                              day.isoformat(), f'SINTETICO-{index:08}', 'Leitura', f'{index % 20:02}',
                              *[f'SINTETICO-{index % 1000}-{j}' for j in range(12)], *([None]*49)])
            book.save(path)
        manifest.append({'file':path.name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(), 'month':day.strftime('%Y-%m')})
        (directory/'manifest.json').write_text(json.dumps(manifest,indent=2))
        print('Planilha sintética', day_index+1, '/50', flush=True)
    (directory/'manifest.json').write_text(json.dumps(manifest,indent=2))


def run(args):
    # Both code versions read identical Excel bytes. Database is always a new temp dir.
    sys.path.insert(0, str(args.code.resolve()))
    with tempfile.TemporaryDirectory(prefix='sabesp-performance-') as folder:
        os.environ['APP_DATA_DIR'] = folder
        import storage, excel_io, core, queries, holidays, cached_queries, fast_reports, exports
        storage.DATA = Path(folder)
        results = {'rows':args.rows,'code':str(args.code), 'synthetic':True,
                   'input_shape':'72 colunas; 23 preenchidas, 49 vazias; arquivos diários de 20.000 linhas',
                   'memory_method':'VmRSS amostrada a cada 20 ms; processo novo por cenário'}
        with storage.connect() as c: pass
        for day,scope,state,town in [('2026-09-07','Nacional','',''),('2026-09-09','Estadual','SP',''),
                                     ('2026-09-10','Municipal','SP','Agudos'),('2026-10-12','Nacional','','')]:
            holidays.save(day,'FERIADO SINTÉTICO DE TESTE',scope,state,town)
        files=json.loads((args.fixtures/'manifest.json').read_text())[:args.rows//20000]
        assert len(files)*20000==args.rows, 'Gere os 50 arquivos antes dos ensaios'
        expected = {}; last_import = None
        profiler=cProfile.Profile() if args.profile else None
        if profiler:profiler.enable()
        with measure(results,'excel_import',sample_memory=profiler is None):
            for entry in files:
                content=(args.fixtures/entry['file']).read_bytes()
                parsed=excel_io.inspect(content)[0]
                added,skipped=storage.import_sheet(content,entry['file'],{**parsed,'records':excel_io.iter_records(content,parsed)},parsed['mapping'],entry['month'])
                assert added==20000 and skipped==0
                last_import=storage.imports(entry['month'])[-1]['id']
                print(args.label,args.rows,entry['file'],'importado',flush=True)
        if profiler:
            profiler.disable()
            stats=pstats.Stats(profiler).strip_dirs()
            results['profile_import']=[{'function':str(key),'primitive_calls':value[0],
                'calls':value[1],'self_seconds':round(value[2],6),'cumulative_seconds':round(value[3],6)}
                for key,value in sorted(stats.stats.items(),key=lambda item:item[1][3],reverse=True)[:40]]
            results['profile_warning']='Instrumentado: os tempos deste arquivo não entram na comparação antes/depois.'
            results['profile_memory_warning']='Importação instrumentada sem thread de amostragem: RSS apenas no início/fim; não usada na comparação de RAM.'
        months=sorted({entry['month'] for entry in files}); month=months[-1]
        prices=storage.month_info(month)['prices']; path=str(storage.DATA); rev=queries.revision()
        with measure(results,'billing_all_months'):
            totals={m:cached_queries.overview(path,rev,m) for m in months}
            results['financial']={m:{'units':s['units'],'holiday_quantity':s['holiday_quantity'],
                                    'total_cents':sum(r['total_cents'] for r in queries.summary(s,prices))} for m,s in totals.items()}
        # Independent old five-rule engine, streaming saved records, without loading the month.
        with measure(results,'financial_regression'):
            with storage.connect() as c:
                for m in months:
                    units={k:0 for k in core.CATEGORIES}
                    holiday_count=0
                    for r in c.execute('SELECT r.raw,i.mapping FROM records r JOIN imports i ON i.id=r.import_id WHERE r.month=?',(m,)):
                        raw=json.loads(r['raw'])
                        value=core.evaluate(raw,json.loads(r['mapping']),m)['units']
                        for key in units: units[key]+=value[key]
                        day=raw[core.FIELDS['date']]; city=raw[core.FIELDS['city']]
                        if raw[core.FIELDS['retained']]=='Não' and not raw[core.FIELDS['cause']] and date.fromisoformat(day).weekday()!=6:
                            if day in ('2026-09-07','2026-10-12') and city!='LOCAL NÃO IDENTIFICADO':holiday_count+=1
                            elif day=='2026-09-09' and city in ('ATC AGUDOS','ATC ARACARIGUAMA'):holiday_count+=1
                            elif day=='2026-09-10' and city=='ATC AGUDOS':holiday_count+=1
                    assert units==totals[m]['units'],(m,units,totals[m]['units'])
                    assert holiday_count==totals[m]['holiday_quantity'],(m,holiday_count,totals[m]['holiday_quantity'])
        with measure(results,'sql_cold_month'):
            queries.overview(month); holidays.overview(month)
        with measure(results,'filter_day'):
            cached_queries.overview(path,rev,month,files[-1]['file'][10:20],files[-1]['file'][10:20])
        with measure(results,'filter_interval'):
            cached_queries.overview(path,rev,month,month+'-01',month+'-15')
        with measure(results,'productivity'):
            products={by:cached_queries.productivity(path,rev,month,prices,by) for by in ('employee','city','group')}
        with measure(results,'page_first'): queries.record_page(month,limit=100)
        with measure(results,'page_last'):
            queries.record_page(month,offset=max(0,totals[month]['total_records']-100),limit=100)
        summary=queries.summary(totals[month],prices)
        report_args=(month,summary,products,storage.imports(month),storage.audit(month),{},False,{})
        with measure(results,'summary_excel'): fast_reports.summary_excel(*report_args)
        with measure(results,'pdf'):
            exports.pdf_report(month,[],prices,{},False,summary_data=summary,productivity_data=products,record_count=totals[month]['total_records'],excluded_count=0)
        with measure(results,'full_excel'):
            output=fast_reports.detailed_excel(storage.DATA/'contrato.sqlite3',rev,month,prices,report_args)
            results['full_excel_bytes']=output.stat().st_size
        with measure(results,'delete_import'):
            storage.set_import_deleted(month,last_import,True,'TESTE SINTÉTICO')
            deleted=cached_queries.overview(path,queries.revision(),month)
            assert deleted['active_count']==totals[month]['active_count']-20000
        with measure(results,'restore_import'):
            storage.set_import_deleted(month,last_import,False,'TESTE SINTÉTICO')
            restored=cached_queries.overview(path,queries.revision(),month)
            assert restored==totals[month]
        with measure(results,'navigation'):
            from streamlit.testing.v1 import AppTest
            app=AppTest.from_file(str(args.code/'app.py'),default_timeout=180).run()
            assert not app.exception
            from datetime import datetime
            app.sidebar.date_input[0].set_value(datetime.strptime(month+'-01','%Y-%m-%d').date()).run()
            results['screens']={}
            for page in ['Painel inicial','Importar planilhas','Fechamento mensal','Produtividade','Relatórios']:
                start=time.perf_counter();app.sidebar.radio[0].set_value(page).run()
                assert not app.exception,(page,app.exception)
                results['screens'][page]=round(time.perf_counter()-start,6)
        with storage.connect() as c:
            assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            results['db_bytes']=(storage.DATA/'contrato.sqlite3').stat().st_size
            results['sql_plan']=[tuple(r) for r in c.execute("EXPLAIN QUERY PLAN SELECT SUM(u138) FROM record_metrics WHERE month=? AND day BETWEEN ? AND ?",(month,month+'-01',month+'-15'))]
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(results,ensure_ascii=False,indent=2))
        print('RESULTADO',args.output,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixtures',type=Path,required=True)
    parser.add_argument('--generate',action='store_true')
    parser.add_argument('--code',type=Path,default=Path(__file__).parent)
    parser.add_argument('--rows',type=int,choices=[20000,100000,500000,1000000])
    parser.add_argument('--label',default='teste')
    parser.add_argument('--profile',action='store_true',help='Instrumenta a importação; não usar os tempos para comparar desempenho')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if args.generate: fixture(args.fixtures)
    elif args.rows and args.output: run(args)
    else: parser.error('Informe --generate ou --rows e --output')
