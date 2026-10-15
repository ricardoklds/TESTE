"""Mede visões gerenciais em fixture isolada; nunca usa a base de produção."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import tempfile
from time import perf_counter
from benchmark_independent_compare import fixture
from validacao_independente import sha
import managerial
import cached_queries


def benchmark(output,rows=500000):
    output=Path(output);output.mkdir(parents=True,exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='sabesp-manager-') as temp:
        data,saved,m,reference=fixture(Path(temp),rows)
        import sqlite3
        with closing(sqlite3.connect(data/'contrato.sqlite3')) as c:
            c.execute("UPDATE record_metrics SET employee='Funcionário '||((id/100)%60),city=CASE (id/20)%5 WHEN 0 THEN 'ATC AGUDOS' WHEN 1 THEN 'ATC ARACARIGUAMA' WHEN 2 THEN 'ATC BOCAINA' WHEN 3 THEN 'ATC ANHEMBI' ELSE 'ATC IBIUNA' END,group_name=printf('%02d',import_id)")
            c.execute("UPDATE records SET raw=json_set(raw,'$.\"Nome do TACE\"','Funcionário '||((id/100)%60),'$.ATC',CASE (id/20)%5 WHEN 0 THEN 'ATC AGUDOS' WHEN 1 THEN 'ATC ARACARIGUAMA' WHEN 2 THEN 'ATC BOCAINA' WHEN 3 THEN 'ATC ANHEMBI' ELSE 'ATC IBIUNA' END,'$.Grupo',printf('%02d',import_id))")
            c.execute("UPDATE holiday_identity_records SET source=(SELECT lower(city) FROM record_metrics WHERE id=holiday_identity_records.id)")
            c.execute('DELETE FROM automatic_localities')
            c.executemany('INSERT INTO automatic_localities VALUES(?,?,?,?,?)',[(source,town,'SP','BR','Localidade sintética de teste') for source,town in [('atc agudos','agudos'),('atc aracariguama','aracariguama'),('atc bocaina',''),('atc anhembi','anhembi'),('atc ibiuna','ibiuna')]])
            c.commit()
        before=sha(data/'contrato.sqlite3');prices={k:m['prices'][k] for k in managerial.UNITS if k!='feriado'};path=str(data)
        times={}
        def measure(name,fn):
            tick=perf_counter();r=fn();times[name]=perf_counter()-tick;return r
        total=measure('overview_seconds',lambda:managerial.overview(path,'2026-09',prices))
        opts=measure('options_seconds',lambda:managerial.options(path,'2026-09'))
        n,rank=measure('employee_top50_seconds',lambda:managerial.page(path,'2026-09',prices))
        combinations,detail=measure('detail_page100_seconds',lambda:managerial.page(path,'2026-09',prices,by=('city','group','employee'),limit=100))
        filters={'city':['ATC AGUDOS'],'group':['01'],'employee':['Funcionário 0']}
        filtered=measure('combined_filter_seconds',lambda:managerial.overview(path,'2026-09',prices,filters=filters))
        measure('dated_period_seconds',lambda:managerial.overview(path,'2026-09',prices,'2026-09-07','2026-09-07'))
        for key,col in managerial.UNITS.items():assert total[col]==reference['independent_quantities'][key]
        parts={}
        with closing(managerial.connect(path)) as c:
            for dim in managerial.DIMS:
                sql,args=managerial.aggregate_sql(c,'2026-09',by=(dim,));sums=dict.fromkeys(managerial.MEASURES,0)
                for row in c.execute(sql,args):
                    for key in sums:sums[key]+=row[key]
                parts[dim]=all(sums[key]==total[key] for key in sums)
        assert all(parts.values())
        measure('excel_all_aggregates_seconds',lambda:managerial.excel(path,'2026-09',prices,None,None,{},m['revision']))
        measure('pdf_summary_seconds',lambda:managerial.pdf(total,'2026-09',None,None,{},rank,detail))
        for _ in range(2):
            tick=perf_counter()
            cached_queries.management_overview(path,m['revision'],'2026-09',prices)
            cached_queries.management_options(path,m['revision'],'2026-09')
            cached_queries.management_page(path,m['revision'],'2026-09',prices)
            cached_queries.management_page(path,m['revision'],'2026-09',prices,by=('city','group','employee'),limit=100)
            times['cached_dashboard_seconds']=perf_counter()-tick
        assert before==sha(data/'contrato.sqlite3')
        report={'synthetic':True,'rows':rows,'employees':n,'detail_combinations':combinations,'option_counts':{k:len(v) for k,v in opts.items()},'times':times,
            'six_quantities_match_fixture':True,'partition_totals_match':parts,'test_bank_unchanged':True,'production_accessed':False,
            'normal_cents':total['normal_cents'],'holiday_cents':total['holiday_cents'],'total_cents':total['total_cents'],
            'limits':'Consultas SQL, agregados, exportação gerencial e chamadas cacheadas. Não mede rede, importação, Excel originais ou renderização no navegador.'}
        (output/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
        print(json.dumps(report,ensure_ascii=False,indent=2))
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);p.add_argument('--rows',type=int,default=500000)
    a=p.parse_args();benchmark(a.output,a.rows)
