"""Compara uma referência auditada fornecida após calcular a visão gerencial (somente leitura)."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import managerial


def validate(data,reference):
    ref=json.loads(Path(reference).read_text(encoding='utf-8'));month=ref['month']
    expected=ref.get('independent_quantities',ref.get('official_quantities'))
    expected_total=ref.get('independent_total_cents',ref.get('official_total_cents'))
    if not expected or type(expected_total) is not int:raise ValueError('Referência não contém resultado calculado válido.')
    with closing(managerial.connect(data)) as c:
        item=c.execute('SELECT prices FROM months WHERE month=?',(month,)).fetchone()
        if not item:raise ValueError('Competência não disponível na base informada.')
        prices=json.loads(item[0]);revision=c.execute('SELECT revision FROM cache_revision WHERE id=1').fetchone()[0]
        sql,args=managerial.aggregate_sql(c,month)
        current=managerial.decorate(c.execute(sql,args).fetchone(),prices)
        partitions={}
        for dim in managerial.DIMS:
            sql,args=managerial.aggregate_sql(c,month,by=(dim,));totals=dict.fromkeys(managerial.MEASURES,0)
            for row in c.execute(sql,args):
                for key in totals:totals[key]+=row[key]
            partitions[dim]=all(totals[k]==current[k] for k in totals)
    result={'month':month,'read_only':True,'revision':revision,'total_cents':current['total_cents'],
        'reference_total_cents':expected_total,'delta_cents':current['total_cents']-expected_total,
        'quantities':{k:current[col] for k,col in managerial.UNITS.items()},
        'delta_quantities':{k:current[col]-expected[k] for k,col in managerial.UNITS.items()},
        'partition_totals_match':partitions}
    result['matches_reference']=result['delta_cents']==0 and all(v==0 for v in result['delta_quantities'].values())
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',default='data');p.add_argument('--reference',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();out=Path(a.output).resolve();root=Path(a.data).resolve()
    if out==root or root in out.parents or out==Path(a.reference).resolve():p.error('Saída deve ficar fora de data e não pode substituir a referência.')
    result=validate(a.data,a.reference)
    with out.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps(result,ensure_ascii=False,indent=2))
