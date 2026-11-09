"""Antes/depois do painel no servidor (AppTest), sem base de produção."""
import argparse
from contextlib import closing
from datetime import date
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from time import perf_counter
import zipfile


def worker(source,data,output,variant):
    sys.path.insert(0,str(Path(source).resolve()));os.environ['APP_DATA_DIR']=str(Path(data).resolve())
    import storage,managerial
    from streamlit.testing.v1 import AppTest
    detail_queries=[];original=managerial.connect
    def trace(path):
        c=original(path)
        c.set_trace_callback(lambda sql:detail_queries.append(sql) if 'r.raw' in sql and 'FROM records' in sql else None)
        return c
    managerial.connect=trace
    at=AppTest.from_file(str(Path(source)/'app.py'),default_timeout=120).run()
    assert not at.exception
    tick=perf_counter();at.sidebar.date_input[0].set_value(date(2026,9,1)).run();cold=perf_counter()-tick
    assert not at.exception
    warm=[]
    for _ in range(3):
        tick=perf_counter();at.run();warm.append(perf_counter()-tick);assert not at.exception
    result={'variant':variant,'server_panel_first_month_seconds':cold,'server_panel_cached_seconds_samples':warm,
        'detail_queries_on_panel_load':len(detail_queries),'financial_total_display':at.metric[0].value,'holiday_value_display':at.metric[2].value}
    assert not detail_queries
    if variant=='after':
        tick=perf_counter();at.button(key='holiday_card_prepare').click().run();result['export_and_ui_seconds']=perf_counter()-tick
        assert not at.exception
        scope,content=at.session_state['holiday_card_file'];result['xlsx_bytes']=len(content)
        result['detail_queries_after_export']=len(detail_queries)
        import openpyxl
        with closing(openpyxl.load_workbook(BytesIO(content),read_only=True)) as book:
            summary=dict(book['Resumo'].values);result['exported_quantity']=summary['Quantidade'];result['exported_total_cents']=round(summary['Valor total (R$)']*100)
            ids=set();n=0
            for sheet in book:
                if not sheet.title.startswith('Leituras '):continue
                values=iter(sheet.values);headers=list(next(values));column=headers.index('ID do registro')
                for row in values:n+=1;ids.add(row[column])
            assert len(ids)==n==summary['Quantidade'];result['export_unique_ids_match_quantity']=True
        # Mesmo arquivo pode ser baixado/reexibido sem consultar detalhes de novo.
        count=len(detail_queries);at.run();assert len(detail_queries)==count
        result['repeat_render_reused_export']=True
    Path(output).write_text(json.dumps(result,ensure_ascii=False,indent=2))


def benchmark(output,rows=500000):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=False)
    from benchmark_independent_compare import fixture
    from validacao_independente import sha
    import storage
    with tempfile.TemporaryDirectory(prefix='sabesp-card-benchmark-') as tmp:
        root=Path(tmp);data,saved,m,reference=fixture(root,rows)
        before=sha(data/'contrato.sqlite3')
        old=root/'before';old.mkdir()
        archive=subprocess.check_output(['git','archive','--format=zip','2b65528'])
        with zipfile.ZipFile(BytesIO(archive)) as z:z.extractall(old)
        results=[]
        for variant,source in [('before',old),('after',Path(__file__).resolve().parent)]:
            target=output/(variant+'.json')
            with (output/(variant+'-progress.txt')).open('w') as log:
                subprocess.run([sys.executable,str(Path(__file__).resolve()),'--worker','--source',str(source),'--data',str(data),'--output',str(target),'--variant',variant],check=True,stdout=log,stderr=subprocess.STDOUT)
            results.append(json.loads(target.read_text()))
        assert before==sha(data/'contrato.sqlite3')
        assert results[0]['financial_total_display']==results[1]['financial_total_display']
        assert results[0]['holiday_value_display']==results[1]['holiday_value_display']
        assert results[1]['exported_quantity']==reference['independent_quantities']['feriado']
        report={'synthetic':True,'rows':rows,'groups':20,'holiday_quantity':rows//21,'before':results[0],'after':results[1],
            'synthetic_bank_unchanged':True,'production_not_accessed':True,
            'scope':'Mesmo banco e Python; versões antes/depois em processos separados. AppTest mede execução da interface no servidor, não navegador/rede. Uma amostra inicial e três cacheadas por versão. Não é uma validação real de setembro.'}
        (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--rows',type=int,default=500000)
    p.add_argument('--worker',action='store_true');p.add_argument('--source');p.add_argument('--data');p.add_argument('--variant')
    a=p.parse_args()
    if a.worker:worker(a.source,a.data,a.output,a.variant)
    else:benchmark(a.output,a.rows)
