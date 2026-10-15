"""Reconciliação somente leitura entre acumulado mensal e antigo filtro das telas."""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import openpyxl
import auditoria_fechamento as audit
import holidays
import periods
import queries


def diagnose(data, output, month='2026-09'):
    data=Path(data).resolve();output=Path(output).resolve()
    if output==data or data in output.parents:
        raise ValueError('A saída deve ficar fora de data.')
    first,last=periods.month_bounds(month);start,end=first.isoformat(),last.isoformat()
    output.mkdir(parents=True,exist_ok=False)
    report={'month':month,'read_only':True,'available':False,
            'code_sha256':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                           for name in ('app.py','queries.py','periods.py','auditoria_fechamento.py','holidays.py')},
            'limits':['Não lê o cache em RAM da instalação Streamlit; compara SQL sem cache em uma transação consistente.',
                      'Não altera registros, projeções, regras, preços, calendário ou fechamento.',
                      'Os valores informados são referências, não resultados desta execução.']}
    if month=='2026-09':
        report['reported']={'audited_cents':59690623,'old_panel_cents':59550945,
                            'difference_cents':139678,'holiday_quantity':19951,'holiday_cents':2094855,
                            'audited_quantities':audit.MANUAL|{'feriado':19951},
                            'old_panel_quantities':audit.REPORTED}
    book=openpyxl.Workbook(write_only=True)
    delta_sheet=audit.Sheets(book,'Registros da diferença',[
        'ID','Importação','Arquivo','Linha original','Grupo','Cidade/ATC','Funcionário','Fornecimento','Execução',
        'Data original','Data projetada','Classe de data','Erros salvos','Motivo da diferença',
        *audit.KEYS,'Diferença (centavos)'])
    summary_sheet=audit.Sheets(book,'Comparação',['Serviço','Acumulado mensal','Filtro antigo das telas',
                                                 'Diferença','Preço (centavos)','Diferença (centavos)'])
    with closing(sqlite3.connect((data/'contrato.sqlite3').as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');c.execute('BEGIN')
        if c.execute('PRAGMA user_version').fetchone()[0]!=5:
            raise ValueError('Exige schema 5. Este diagnóstico não executa migrações.')
        report['available_months']=[r[0] for r in c.execute('SELECT month FROM months ORDER BY month')]
        info=c.execute('SELECT * FROM months WHERE month=?',(month,)).fetchone()
        if info:
            report['available']=True;report['closed']=bool(info['closed'])
            report['revision']=c.execute('SELECT revision FROM cache_revision WHERE id=1').fetchone()[0]
            prices=json.loads(info['prices'])|{'feriado':105}
            report['prices_cents']=prices
            monthly=queries.overview(month,connection=c)
            filtered=queries.overview(month,start,end,connection=c)
            charge_sql,args=holidays.charges_query(c,month)
            monthly['units']['feriado']=c.execute('SELECT COUNT(*) FROM ('+charge_sql+')',args).fetchone()[0]
            fee_period,fee_args=holidays.charges_query(c,month,start,end)
            filtered['units']['feriado']=c.execute('SELECT COUNT(*) FROM ('+fee_period+')',fee_args).fetchone()[0]
            report['monthly_quantities']=monthly['units'];report['old_screen_quantities']=filtered['units']
            report['monthly_cents']=sum(monthly['units'][k]*prices[k] for k in audit.KEYS)
            report['old_screen_cents']=sum(filtered['units'][k]*prices[k] for k in audit.KEYS)
            report['delta_cents']=report['monthly_cents']-report['old_screen_cents']
            report['missing_projected_date']=monthly['undated']
            for k in audit.KEYS:
                a,b=monthly['units'][k],filtered['units'][k]
                summary_sheet.append([k,a,b,a-b,prices[k],(a-b)*prices[k]])
            # IDs/units only for rows removed by the old period predicate. No full bank in RAM.
            predicate='m.month=? AND m.excluded=0 AND m.import_deleted=0 AND (m.day IS NULL OR m.day<? OR m.day>? OR m.errors<>0)'
            cols=','.join('m.'+v for v in queries.COLS.values())
            sql='''WITH fees AS ('''+charge_sql+''') SELECT m.id,m.import_id,m.day,m.errors,m.group_name,m.city,m.employee,
                '''+cols+''',r.raw,r.result,r.line,i.name,i.mapping,
                CASE WHEN f.id IS NOT NULL AND (m.day IS NULL OR m.day<? OR m.day>?) THEN 1 ELSE 0 END fee_delta
                FROM record_metrics m LEFT JOIN records r ON r.id=m.id
                LEFT JOIN imports i ON i.id=m.import_id LEFT JOIN fees f ON f.id=m.id WHERE '''+predicate+' ORDER BY m.id'
            delta=Counter();reasons=Counter();n=0
            for row in c.execute(sql,[*args,start,end,month,start,end]):
                raw=json.loads(row['raw']) if row['raw'] else {}
                result=json.loads(row['result']) if row['result'] else {}
                mapping=json.loads(row['mapping']) if row['mapping'] else {}
                units={k:row[v] or 0 for k,v in queries.COLS.items()};units['feriado']=row['fee_delta']
                if not any(units.values()):continue
                n+=1;delta.update(units)
                reason=('Sem data projetada' if row['day'] is None else
                        'Data projetada fora do mês' if not start<=row['day']<=end else 'Erros: filtro antigo exige errors=0')
                reasons[reason]+=1
                delta_sheet.append([row['id'],row['import_id'],row['name'],row['line'],row['group_name'],row['city'],row['employee'],
                    raw.get(mapping.get('supply')),raw.get(mapping.get('task')),str(raw.get(mapping.get('date'))),row['day'],
                    audit.date_class(raw,mapping,month),'; '.join(result.get('errors',[])),reason,
                    *[units[k] for k in audit.KEYS],sum(units[k]*prices[k] for k in audit.KEYS)])
                if n%10000==0:print(f'{n} registros de diferença exportados…',flush=True)
            report['delta_records']=n;report['delta_reasons']=dict(reasons)
            report['detail_delta_quantities']={k:delta[k] for k in audit.KEYS}
            report['detail_matches_sql']=all(delta[k]==monthly['units'][k]-filtered['units'][k] for k in audit.KEYS)
            # Independent audit SQL: same five sums used by auditoria_fechamento.py.
            sums=c.execute('SELECT '+','.join('COALESCE(SUM('+v+'),0)' for v in queries.COLS.values())+
                ' FROM record_metrics WHERE month=? AND excluded=0 AND import_deleted=0',(month,)).fetchone()
            report['audit_sql_matches_monthly']=all(sums[i]==monthly['units'][k] for i,k in enumerate(queries.COLS))
            if 'reported' in report:
                report['matches_reported_totals']=(report['monthly_cents']==59690623 and report['old_screen_cents']==59550945)
                report['matches_reported_holidays']=monthly['units']['feriado']==19951
                report['matches_reported_quantities']=(monthly['units']==report['reported']['audited_quantities'] and
                                                       filtered['units']==report['reported']['old_panel_quantities'])
        else:
            report['limits'].append('Mês ausente: não foi possível comprovar os registros ou o valor da divergência real.')
    meta=audit.Sheets(book,'Evidências',['Campo','Valor'])
    for key,value in report.items():meta.append([key,json.dumps(value,ensure_ascii=False)])
    book.save(output/'reconciliacao.xlsx')
    (output/'resultado.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'RELATORIO.md').write_text('# Reconciliação somente leitura\n\n'
        'Comprovado no código: a tela antiga aplicava BETWEEN e errors=0 mesmo em Mês completo. '
        'O acumulado mensal e a auditoria não aplicam esse recorte de visualização.\n\n'
        'A correção usa o acumulado mensal para Mês completo. Dia e intervalo preservam seus critérios.\n\n'
        'Resultados desta base (centavos inteiros; nenhum total forçado):\n\n```json\n'+
        json.dumps(report,ensure_ascii=False,indent=2)+'\n```\n\n'
        'Consulte reconciliacao.xlsx para os IDs e motivos da diferença. '
        'Não atribua a diferença aos registros sem data sem confirmar detail_matches_sql e os totais.\n',encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',default='data');p.add_argument('--month',default='2026-09');p.add_argument('--output',required=True)
    a=p.parse_args();r=diagnose(a.data,a.output,a.month)
    print(f'Concluído. Mês disponível: {r["available"]}. Nenhum dado alterado. Saída: {a.output}')
