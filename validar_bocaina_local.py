"""Conferência local somente leitura. Nunca migra ou atualiza o banco.

Uso: python validar_bocaina_local.py --data data --output conferencia-bocaina.json
"""
from contextlib import closing
import argparse
import json
from pathlib import Path
import sqlite3
from unittest.mock import patch
import core,localities,holiday_review


def validate(data,month='2026-09'):
    path=Path(data)/'contrato.sqlite3'
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row;c.execute('BEGIN')
        if c.execute('PRAGMA user_version').fetchone()[0]!=5:
            raise ValueError('O verificador exige banco versão 5. Não executa migrações.')
        info=c.execute('SELECT prices FROM months WHERE month=?',(month,)).fetchone()
        if not info:return {'month':month,'available':False,'reason':'Mês não disponível nessa base; os 834 registros não foram testados.'}
        with patch.object(localities,'municipal_confirmations',return_value=()):
            old,old_args=holiday_review.review_sql(c,month)
        new,new_args=holiday_review.review_sql(c,month)
        def totals(sql,args):
            row=c.execute('SELECT COALESCE(SUM(charged),0) charged,COALESCE(SUM(pending),0) pending FROM ('+sql+')',args).fetchone()
            return dict(row)
        before=totals(old,old_args);after=totals(new,new_args)
        old_ids='SELECT id FROM ('+old+') WHERE charged=1'
        new_ids='SELECT id FROM ('+new+') WHERE charged=1'
        changed=c.execute('SELECT COUNT(*) FROM ('+old_ids+' EXCEPT '+new_ids+')',[*old_args,*new_args]).fetchone()[0]
        changed+=c.execute('SELECT COUNT(*) FROM ('+new_ids+' EXCEPT '+old_ids+')',[*new_args,*old_args]).fetchone()[0]
        categories={'138':'u138','128':'u128','137':'u137','impressao':'uprint','apontamento':'uop'}
        row=c.execute('SELECT '+','.join('COALESCE(SUM('+col+'),0) "'+k+'"' for k,col in categories.items())+
                      ' FROM record_metrics WHERE month=? AND excluded=0 AND import_deleted=0',(month,)).fetchone()
        prices=json.loads(info['prices']);five=sum(row[k]*prices[k] for k in categories)
        bocaina=list(c.execute('SELECT r.day,r.status,COUNT(*) n FROM ('+new+') r JOIN holiday_identity_records p ON p.id=r.id '+
                               "WHERE p.source='atc bocaina' GROUP BY r.day,r.status ORDER BY r.day,r.status",new_args))
        return {'month':month,'available':True,'synthetic':False,'before':before,'after':after,
                'charged_ids_changed':changed,'financial_before_cents':five+before['charged']*105,
                'financial_after_cents':five+after['charged']*105,'five_units':dict(row),
                'bocaina_by_day_status':[dict(r) for r in bocaina],
                'financial_unchanged':changed==0 and before['charged']==after['charged'],
                'read_only':True}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',default='data');p.add_argument('--month',default='2026-09');p.add_argument('--output',required=True)
    a=p.parse_args();result=validate(a.data,a.month)
    out=Path(a.output).resolve();data=Path(a.data).resolve()
    if out==data or data in out.parents:raise ValueError('Salve o relatório fora de data para preservar a pasta original.')
    if out.suffix.lower()!='.json':raise ValueError('Use um arquivo .json novo para o relatório.')
    with out.open('x',encoding='utf-8') as file:file.write(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result['available'] and not result['financial_unchanged']:raise SystemExit(2)
