"""Medições reproduzíveis. --load cria fixture ARTIFICIAL temporária de escala.

Não contém os 174 mil registros do computador do usuário e não estima resultados
de negócio. Apenas mede desempenho; nunca escreve na base de produção.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
try:
    import resource
except ImportError:
    resource=None  # Windows: timing still works, peak RSS is explicitly unavailable.
import sqlite3
import tempfile
import time
import core,storage,queries,cached_queries,periods,fast_reports
from exports import pdf_report

def run(load=0):
    source=storage.DATA;temp=None;output={'artificial_load_fixture':bool(load),'stages':{}}
    def measure(name,fn):
        t=time.perf_counter();result=fn();output['stages'][name]=round(time.perf_counter()-t,4);return result
    if load:
        temp=tempfile.TemporaryDirectory();storage.DATA=Path(temp.name)
        with closing(sqlite3.connect(source/'contrato.sqlite3')) as src,closing(sqlite3.connect(storage.DATA/'contrato.sqlite3')) as dst:src.backup(dst)
        with closing(storage.connect()) as c:
            templates=c.execute('SELECT r.*,m.day,m.employee,m.city,m.group_name,m.business_key,m.errors,m.alerts,m.u138,m.u128,m.u137,m.uprint,m.uop FROM records r JOIN record_metrics m ON m.id=r.id WHERE r.month=? ORDER BY r.id',('2026-10',)).fetchall()
            mappings={r['id']:json.loads(r['mapping']) for r in c.execute('SELECT id,mapping FROM imports')}
            base=len(templates)
            if load<base:raise ValueError('A carga deve ser maior que a base real.')
            c.execute('DROP TRIGGER metrics_insert')
            start=time.perf_counter();raw_batch=[];metric_batch=[]
            for new_id in range(base+1,load+1):
                r=templates[(new_id-1)%base];raw=json.loads(r['raw']);result=json.loads(r['result'])
                mapping=mappings[r['import_id']]
                raw[mapping['supply']]='LOAD-TEST-'+str(new_id)
                result['key']='|'.join(str(raw.get(mapping[k]) or '') for k in ('supply','date','task'))
                raw_batch.append((new_id,r['month'],r['import_id'],r['line'],'ARTIFICIAL-'+str(new_id),json.dumps(raw,ensure_ascii=False),json.dumps(result,ensure_ascii=False),r['excluded'],r['reason'],r['import_deleted']))
                metric_batch.append((new_id,r['month'],r['import_id'],r['day'],r['employee'],r['city'],r['group_name'],result['key'],r['errors'],r['alerts'],r['u138'],r['u128'],r['u137'],r['uprint'],r['uop'],r['excluded'],r['import_deleted']))
                if len(raw_batch)==1000 or new_id==load:
                    c.executemany('INSERT INTO records VALUES (?,?,?,?,?,?,?,?,?,?)',raw_batch)
                    c.executemany('INSERT INTO record_metrics VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',metric_batch)
                    raw_batch=[];metric_batch=[]
                if new_id%100000==0:print(f'CARGA ARTIFICIAL: {new_id} linhas',flush=True)
            c.commit();output['fixture_build_seconds']=round(time.perf_counter()-start,3)
    try:
        month='2026-10';prices=storage.month_info(month)['prices'];revision=queries.revision();path=str(storage.DATA.resolve())
        overview=measure('monthly_sql_cold',lambda:queries.overview(month));output['records']=overview['total_records']
        measure('daily_sql_cold',lambda:queries.overview(month,'2026-10-10','2026-10-10'))
        measure('record_page_100',lambda:queries.record_page(month,'2026-10-01','2026-10-31',limit=100))
        measure('record_last_page_100',lambda:queries.record_page(month,offset=max(0,overview['total_records']-100),limit=100))
        products={by:measure('ranking_'+by,lambda by=by:queries.productivity(month,prices,by)) for by in ('employee','city','group')}
        measure('monthly_cache_fill',lambda:cached_queries.overview(path,revision,month))
        measure('monthly_cache_hit',lambda:cached_queries.overview(path,revision,month))
        summary=queries.summary(overview,prices)
        args=(month,summary,products,storage.imports(month),storage.audit(month),{},False,{})
        measure('summary_excel',lambda:fast_reports.summary_excel(*args))
        measure('summary_pdf',lambda:pdf_report(month,[],prices,{},False,summary_data=summary,productivity_data=products,record_count=overview['total_records'],excluded_count=overview['excluded_count']))
        from streamlit.testing.v1 import AppTest
        at=measure('initial_screen',lambda:AppTest.from_file(str(Path(__file__).parent/'app.py'),default_timeout=120).run())
        assert not at.exception
        for page in ['Importar planilhas','Fechamento mensal','Produtividade','Relatórios','Painel inicial']:
            measure(page,lambda page=page:at.sidebar.radio[0].set_value(page).run(timeout=120));assert not at.exception
        at.sidebar.radio[0].set_value('Painel inicial').run()
        at.radio(key='period_mode').set_value('Dia específico').run()
        from datetime import date
        measure('day_filter_ui',lambda:at.date_input(key='period_day_2026-10').set_value(date(2026,10,10)).run(timeout=120));assert not at.exception
        output['peak_rss_mib']=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024,2) if resource else None
        return output
    finally:
        storage.DATA=source
        if temp:temp.cleanup()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--load',type=int,default=0);parser.add_argument('--output',default='benchmark-results.json');args=parser.parse_args()
    output=run(args.load);Path(args.output).write_text(json.dumps(output,indent=2,ensure_ascii=False));print(json.dumps(output,indent=2,ensure_ascii=False))
