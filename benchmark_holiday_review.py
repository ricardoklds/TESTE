"""Mede consultas da conferência com 1 milhão de linhas sintéticas, sem Excel.

Cria banco relacional temporário por SQL. Não mede importação nem dados da empresa.
Uso: .venv/bin/python benchmark_holiday_review.py --output /tmp/review.json
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import tempfile
import time
import core,storage,holidays,holiday_review,queries
import cached_queries


def run(output):
    previous=storage.DATA
    try:
        with tempfile.TemporaryDirectory(prefix='holiday-review-load-') as directory:
            storage.DATA=Path(directory)
            with closing(storage.connect()) as c:
                # Bypass insert triggers ONLY in this disposable synthetic fixture.
                definitions=[r[0] for r in c.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name IN ('metrics_insert','holiday_identity_insert','automatic_locality_insert')")]
                for name in ('metrics_insert','holiday_identity_insert','automatic_locality_insert'):c.execute('DROP TRIGGER '+name)
                raw=dict(zip(core.FIELDS.values(),['Sim','Não',None,0,None,'TESTE','ATC AGUDOS','2026-09-07','TESTE','Leitura','01']))
                result=core.evaluate(raw,core.FIELDS,'2026-09')
                prices={k:v[2] for k,v in core.CATEGORIES.items()}
                c.execute('INSERT INTO months(month,prices) VALUES(?,?)',('2026-09',json.dumps(prices)))
                c.execute('INSERT INTO imports(month,name,sha,sheet,mapping,headers,created_at) VALUES(?,?,?,?,?,?,?)',('2026-09','FIXTURE SQL — não é importação Excel','SINTETICO','TESTE',json.dumps(core.FIELDS),json.dumps(list(raw)),storage.now()))
                c.execute('''WITH RECURSIVE sequence(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM sequence WHERE n<1000000)
                    INSERT INTO records(id,month,import_id,line,fingerprint,raw,result)
                    SELECT n,'2026-09',1,n+1,'FINGERPRINT SINTETICO-'||n,
                    json_set(?, '$."Codigo do Fornecimento"','TESTE-'||n,'$.ATC',CASE WHEN n%7=0 THEN 'ORIGEM DESCONHECIDA' ELSE 'ATC AGUDOS' END,
                    '$."Data da Leitura Atual"',date('2026-09-01','+'||((n-1)%30)||' days')),
                    json_set(?,'$.city',CASE WHEN n%7=0 THEN 'ORIGEM DESCONHECIDA' ELSE 'ATC AGUDOS' END,
                    '$.key','TESTE-'||n||'|'||date('2026-09-01','+'||((n-1)%30)||' days')||'|Leitura') FROM sequence''',(json.dumps(raw),json.dumps(result)))
                c.execute('''INSERT INTO record_metrics SELECT id,month,import_id,json_extract(raw,'$."Data da Leitura Atual"'),
                    'TESTE',json_extract(raw,'$.ATC'),'01',json_extract(result,'$.key'),0,0,1,0,0,0,0,0,0 FROM records''')
                c.execute('''INSERT INTO holiday_identity_records SELECT id,'TESTE-'||id,'Leitura',
                    CASE WHEN id%7=0 THEN 'origem desconhecida' ELSE 'atc agudos' END,1 FROM records''')
                for sql in definitions:c.execute(sql)
                # Actual locality resolution from the existing reference, no assumed match.
                c.execute('''INSERT INTO automatic_localities SELECT source,json_extract(resolve_locality(source),'$[0]'),
                    json_extract(resolve_locality(source),'$[1]'),json_extract(resolve_locality(source),'$[2]'),json_extract(resolve_locality(source),'$[3]')
                    FROM (SELECT DISTINCT source FROM holiday_identity_records)''')
                c.commit()
            holidays.save('2026-09-07','FERIADO SINTÉTICO','Nacional')
            before=(queries.overview('2026-09'),holidays.overview('2026-09'))
            measurements={}
            for situation in holiday_review.SITUATIONS:
                begin=time.perf_counter()
                count,rows=holiday_review.page('2026-09',limit=100,situation=situation)
                measurements[situation]={'seconds':round(time.perf_counter()-begin,6),'count':count,'page_rows':len(rows)}
                print(situation,measurements[situation],flush=True)
            begin=time.perf_counter();summary=holiday_review.pending_summary('2026-09')
            measurements['summary_seconds']=round(time.perf_counter()-begin,6)
            cached_times={};revision=queries.revision();path=str(storage.DATA)
            for situation in holiday_review.SITUATIONS:
                begin=time.perf_counter()
                cached_queries.holiday_page(path,revision,'2026-09',None,None,0,100,situation=situation)
                cached_times[situation]=round(time.perf_counter()-begin,6)
            begin=time.perf_counter();cached_queries.holiday_pending_summary(path,revision,'2026-09',None,None)
            cached_times['pending_summary_seconds']=round(time.perf_counter()-begin,6)
            begin=time.perf_counter();cached_queries.holiday_page(path,revision,'2026-09',None,None,0,100,situation='Pendências')
            cached_times['warm_pending_page_seconds']=round(time.perf_counter()-begin,6)
            assert sum(r['Quantidade'] for r in summary)==before[1]['holiday_pending']
            assert measurements['Elegíveis cobrados']['count']==before[1]['holiday_quantity']
            assert (queries.overview('2026-09'),holidays.overview('2026-09'))==before
            with closing(storage.connect()) as c:
                assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
            report={'synthetic':True,'rows':1000000,'method':'SQL fixture, one month, 30 days, one run, no Excel import measured, no browser measured',
                    'measurements':measurements,'cached_endpoint_seconds':cached_times,'pending_summary':summary,'financial_totals_unchanged':True,'integrity_check':'ok'}
            Path(output).write_text(json.dumps(report,ensure_ascii=False,indent=2))
    finally:storage.DATA=previous


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True)
    run(parser.parse_args().output)
