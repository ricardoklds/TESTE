"""Benchmark isolado da comparação; não mede importação nem recálculo de Excel."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import time
import hashlib
import storage
import validacao_independente as validation


def fixture(folder,n):
    data=folder/'data';old=storage.DATA;storage.DATA=data
    try:
        with closing(storage.connect()) as c:
            # Exclusivamente no banco SINTÉTICO deste benchmark.
            for r in c.execute("SELECT name FROM sqlite_master WHERE type='trigger'").fetchall():
                c.execute('DROP TRIGGER "'+r[0].replace('"','""')+'"')
            prices={'138':138,'128':128,'137':137,'impressao':50,'apontamento':50}
            c.execute('INSERT INTO months(month,prices) VALUES(?,?)',('2026-09',json.dumps(prices)))
            mapping=json.dumps(dict(printed='Faturas Impressas',retained='Fatura Retida',cause='Causas de Leitura/Não Leitura Atual',copies='Quantidade comunicados impressos',operational='CO1 Atual',date='Data da Leitura Atual',supply='Codigo do Fornecimento',task='Tarefa',city='ATC',group='Grupo',employee='Nome do TACE'))
            for i in range(1,21):
                c.execute('INSERT INTO imports(month,name,sha,sheet,mapping,headers,created_at) VALUES(?,?,?,?,?,?,?)',
                    ('2026-09',f'grupo-sintetico-{i}.xlsx',f'{i:064x}','Leituras',mapping,json.dumps(list(json.loads(mapping).values())),'2026-01-01'))
            # 379.523 linhas largas, 20 grupos. A cada 21 execuções, um feriado.
            c.execute('''WITH RECURSIVE seq(i) AS (VALUES(1) UNION ALL SELECT i+1 FROM seq WHERE i<?)
                INSERT INTO records(month,import_id,line,fingerprint,raw,result)
                SELECT '2026-09',1+(i-1)%20,i+1,printf('%064x',i),
                    json_object('Codigo do Fornecimento',CAST(i AS TEXT),'Tarefa','Leitura','ATC','ATC AGUDOS',
                      'Fatura Retida','Não','Faturas Impressas',CASE WHEN i%2=0 THEN 'Sim' ELSE 'Não' END,
                      'Causas de Leitura/Não Leitura Atual','','Quantidade comunicados impressos',2,'CO1 Atual','0',
                      'Data da Leitura Atual',CASE WHEN i%21=0 THEN '2026-09-07' ELSE '2026-09-10' END,
                      'Nome do TACE','Funcionário sintético','Grupo',CAST(1+(i-1)%20 AS TEXT),'Conteúdo sintético',?),
                    json_object('units',json_object('138',i%2=0,'128',i%2<>0,'137',0,'impressao',2,'apontamento',1),'errors',json('[]'))
                FROM seq''',(n,'x'*512))
            c.execute('''INSERT INTO record_metrics SELECT id,month,import_id,
                CASE WHEN id%21=0 THEN '2026-09-07' ELSE '2026-09-10' END,'Funcionário sintético','ATC AGUDOS',
                CAST(import_id AS TEXT),CAST(id AS TEXT),0,0,id%2=0,id%2<>0,0,2,1,0,0 FROM records''')
            c.execute("INSERT INTO holiday_identity_records SELECT id,CAST(id AS TEXT),'Leitura','atc agudos',1 FROM records")
            c.execute("INSERT INTO automatic_localities VALUES('atc agudos','agudos','SP','BR','Cadastro sintético de teste')")
            c.execute("INSERT INTO holidays(day,description,scope,state,municipality) VALUES('2026-09-07','Feriado sintético','Nacional','','')")
            c.commit()
    finally:storage.DATA=old
    saved=folder/'saved';saved.mkdir();manifest=validation.export_inputs(data,saved,'2026-09')
    m=json.loads(manifest.read_text())
    quantities={'138':n//2,'128':n-n//2,'137':0,'impressao':n*2,'apontamento':n,'feriado':n//21}
    # Stub analítico da fixture, NÃO resultado de uma auditoria de dados reais.
    result={'month':'2026-09','prices':m['prices'],'independent_quantities':quantities,
            'independent_total_cents':sum(quantities[k]*m['prices'][k] for k in validation.KEYS),
            'manifest_sha256':validation.sha(manifest),'calculation_completed_before_comparison':True}
    (saved/'calculo_independente.json').write_text(json.dumps(result))
    return data,saved,m,result


def benchmark(output,rows=379523,baseline_timeout=10):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='bench-sabesp-compare-') as tmp:
        temp=Path(tmp);data,saved,m,independent=fixture(temp,rows)
        bank=data/'contrato.sqlite3';before=validation.sha(bank)
        old_source=subprocess.check_output(['git','show','3a62b0e:validacao_independente.py'],text=True)
        start=old_source.index('def compare(data,');end=old_source.index('\n\ndef reports(',start)
        baseline={'completed':False,'records_transferred':0,'timeout_seconds':baseline_timeout};tick=time.perf_counter();captured={}
        def limited_ro(path):
            c=validation.ro(path)
            def row_factory(cursor,row):
                if len(cursor.description)==10 and cursor.description[0][0]=='fingerprint':baseline['records_transferred']+=1
                return sqlite3.Row(cursor,row)
            c.row_factory=row_factory;c.set_progress_handler(lambda:int(time.perf_counter()-tick>=baseline_timeout),10000)
            c.set_trace_callback(lambda sql:captured.update(old=sql) if sql.startswith('WITH fees AS (') else None)
            return c
        namespace={'ro':limited_ro,'closing':closing,'json':json,'KEYS':validation.KEYS,'METRICS':validation.METRICS}
        exec(old_source[start:end],namespace)
        print('Medindo comparação antiga, com limite explícito de tempo...',flush=True)
        with closing(sqlite3.connect(temp/'old.sqlite3')) as scratch:
            try:
                namespace['compare'](data,m,dict(independent),scratch)
                baseline['completed']=True
            except sqlite3.OperationalError as error:
                if 'interrupted' not in str(error):raise
                baseline['interrupted_by_benchmark_timeout']=True
        baseline['elapsed_seconds']=time.perf_counter()-tick
        with closing(validation.ro(data)) as c:
            old_plan=[r[3] for r in c.execute('EXPLAIN QUERY PLAN '+captured['old'])]
        print('Antiga:',baseline,flush=True)
        with closing(sqlite3.connect(temp/'new.sqlite3')) as scratch:
            tick=time.perf_counter();result=dict(independent)
            validation.compare(data,m,result,scratch)
            optimized=dict(result['comparison']);optimized['measured_seconds']=time.perf_counter()-tick
            indexed_plan=[r[3] for r in scratch.execute('EXPLAIN QUERY PLAN UPDATE app SET fee=1 WHERE id IN (SELECT id FROM charged_ids)')]
            assert all(v==0 for v in optimized['delta_quantities'].values())
        tick=time.perf_counter();resumed=validation.compare_saved(data,saved,temp/'resumed')
        resumed_seconds=time.perf_counter()-tick
        assert all(v==0 for v in resumed['comparison']['delta_quantities'].values())
        assert validation.sha(bank)==before
        report={'synthetic':True,'rows':rows,'groups':20,'holiday_rows':rows//21,
            'fixture_bank_bytes':bank.stat().st_size,'baseline':baseline,'optimized':optimized,
            'resume_aggregate_seconds_including_exports':resumed_seconds,'production_not_accessed':True,
            'test_bank_unchanged':True,'sqlite_version':sqlite3.sqlite_version,
            'old_query_plan':old_plan,'optimized_temporary_join_plan':indexed_plan,
            'limits':'Fixture SQL analítica de comparação, não importação/recálculo de Excel. Se a antiga foi interrompida, seu tempo total NÃO foi medido nem extrapolado.'}
        (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True)
    p.add_argument('--rows',type=int,default=379523);p.add_argument('--baseline-timeout',type=float,default=10)
    a=p.parse_args();benchmark(a.output,a.rows,a.baseline_timeout)
