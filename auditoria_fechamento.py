"""Auditoria independente somente leitura. Não migra, resolve ou grava no contrato.

Execute com o aplicativo fechado. Relatórios vão para uma pasta NOVA fora de data.
"""
import argparse
from collections import Counter
from contextlib import closing
from datetime import date
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import openpyxl
import core,periods,holidays,holiday_review,excel_io,localities
from fast_reports import text_row

KEYS=tuple(core.CATEGORIES)+('feriado',)
PRICES={k:v[2] for k,v in core.CATEGORIES.items()}|{'feriado':105}
MANUAL={'138':303350,'137':2680,'128':69161,'feriado':19955,'impressao':79466,'apontamento':50808}
REPORTED={'138':303203,'137':2680,'128':68972,'feriado':19951,'impressao':78546,'apontamento':49824}
METRICS={'138':'u138','128':'u128','137':'u137','impressao':'uprint','apontamento':'uop'}


def date_class(raw,mapping,month):
    column=mapping.get('date')
    if not column:return 'Coluna de data não mapeada'
    if column not in raw:return 'Coluna mapeada ausente nos dados'
    value=raw[column]
    if value is None or isinstance(value,str) and not value.strip():return 'Data vazia'
    if isinstance(value,str) and value.startswith('='):return 'Fórmula na data'
    parsed=periods.parse_date(value)
    if parsed is None:
        return 'Número/serial sem conversão aceita' if isinstance(value,(float,int)) else 'Data inválida ou formato não reconhecido'
    if parsed.strftime('%Y-%m')!=month:return 'Data fora do mês de referência'
    if core.reading_month(value)=='inválida':return 'Data interpretável; formato rejeitado pelo motor'
    return 'Data válida no mês'


def comparison(actual=None,prices=None):
    prices=prices or PRICES
    return [{'Serviço':k,'Categoria':core.CATEGORIES[k][1] if k!='feriado' else 'Adicional de leitura em feriado',
             'Código':core.CATEGORIES[k][0] if k!='feriado' else '200014097','Preço informado (centavos)':PRICES[k],
             'Manual informado':MANUAL[k],'Aplicativo informado':REPORTED[k],
             'Diferença informada':MANUAL[k]-REPORTED[k],
             'Diferença informada (centavos)':(MANUAL[k]-REPORTED[k])*PRICES[k],
             'Aplicativo auditado':actual[k] if actual is not None else None,
             'Auditado menos aplicativo informado':actual[k]-REPORTED[k] if actual is not None else None,
             'Preço da base (centavos)':prices[k],
             'Valor auditado (centavos)':actual[k]*prices[k] if actual is not None else None}
            for k in KEYS]


class Sheets:
    def __init__(self,book,name,headers):
        self.book=book;self.name=name;self.headers=headers;self.index=0;self.rows=1048575
    def append(self,row):
        if self.rows>=1048575:
            self.index+=1;suffix=f' {self.index}';self.sheet=self.book.create_sheet(self.name[:31-len(suffix)]+suffix)
            text_row(self.sheet,self.headers);self.rows=0
        text_row(self.sheet,row);self.rows+=1


def row_reasons(raw,mapping,result,units,active):
    reasons={}
    for key in core.CATEGORIES:
        if not active:reason='Fora do fechamento: registro/importação excluído logicamente'
        elif result['errors']:reason='Erros do registro: '+'; '.join(result['errors'])
        elif units[key]:reason='Contabilizado pelas regras salvas'
        elif key in ('138','128','137'):
            reason='Retida='+str(raw.get(mapping.get('retained')))+'; impressa='+str(raw.get(mapping.get('printed')))+'; causa='+repr(raw.get(mapping.get('cause')))
        elif key=='impressao':reason='Quantidade de comunicados zero/vazia ou sem unidades salvas'
        else:reason='CO1 Atual vazia após normalização, ou sem unidade salva'
        reasons[key]=reason
    return reasons


def holiday_reason(row,raw,mapping,holiday_days):
    if row['review_reason']:return row['review_reason']
    if row['excluded'] or row['import_deleted']:return 'Registro/importação excluído logicamente'
    if row['day'] is None:return 'Sem data interpretável na projeção: não entra na apuração de feriado'
    if core.norm(raw.get(mapping.get('retained')))!='nao':return 'Fatura Retida diferente de Não'
    if core.norm(raw.get(mapping.get('cause'))):return 'Causa preenchida'
    if row['day'] not in holiday_days:return 'Nenhum feriado cadastrado na data da projeção'
    if row['identity_id'] is None:return 'Identidade do adicional ausente: inconsistência a investigar'
    return 'Não contabilizado pela consulta de abrangência/localidade; confira o calendário e a identidade, sem presumir elegibilidade'


def audit(data,output,month='2026-09',check_originals=True):
    if month!='2026-09':raise ValueError('Os valores manuais fornecidos referem-se apenas a setembro/2026.')
    date.fromisoformat(month+'-01')
    data=Path(data).resolve();output=Path(output).resolve()
    if output==data or data in output.parents:raise ValueError('A pasta de saída deve ficar fora de data.')
    output.mkdir(parents=True,exist_ok=False)  # Never overwrite a previous audit.
    report={'month':month,'read_only':True,'manual_records_not_provided':True,'available':False,
            'claimed_manual_cents':59691043,'claimed_app_cents':59550945,'claimed_difference_cents':140098,'claimed_missing_date_records':1606,
            'comparison':comparison(),'proven':['As quantidades e preços informados somam exatamente os dois totais e a diferença de 140098 centavos.'],
            'hypotheses':['Os 1606 registros podem ter causas de data distintas; não se pode atribuir a diferença a eles sem conferir a base.',
                          'Os quatro feriados de diferença não podem ser identificados individualmente sem a lista manual de fornecimento/data/execução.'],
            'imports':[]}
    report['code_sha256']={name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
        for name in ['auditoria_fechamento.py','core.py','periods.py','holidays.py','holiday_review.py','localities.py','municipal_review.py','reference_data/municipalities.json','reference_data/municipal_confirmations.json']}
    book=openpyxl.Workbook(write_only=True)
    with closing(sqlite3.connect((data/'contrato.sqlite3').as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row;c.execute('BEGIN')
        if c.execute('PRAGMA user_version').fetchone()[0]!=5:raise ValueError('Exige schema versão 5; auditoria não executa migrações.')
        info=c.execute('SELECT * FROM months WHERE month=?',(month,)).fetchone()
        if info:
            report['available']=True;report['closed']=bool(info['closed'])
            report['revision']=c.execute('SELECT revision FROM cache_revision WHERE id=1').fetchone()[0]
            prices=json.loads(info['prices'])|{'feriado':105};report['prices']=prices
            print('Auditando registros e seis regras, sem gravar na base…',flush=True)
            with tempfile.TemporaryDirectory(prefix='auditoria-sabesp-') as temp,closing(sqlite3.connect(Path(temp)/'scratch.sqlite3')) as scratch:
                # Diagnostic tables are ONLY in a disposable separate database, never in production.
                scratch.executescript('''CREATE TABLE rows(id INTEGER,import_id INTEGER,line INTEGER,fp TEXT,active INTEGER,
                    grp TEXT,city TEXT,geo TEXT,employee TEXT,day TEXT,date_class TEXT,business TEXT,execution_key TEXT,
                    u138 INTEGER,u128 INTEGER,u137 INTEGER,uprint INTEGER,uop INTEGER,fee INTEGER,total INTEGER);
                    CREATE TABLE original_seen(import_id INTEGER,fp TEXT,line INTEGER,PRIMARY KEY(import_id,fp));''')
                headers=['ID','Importação','Arquivo','Linha original','Ativo','Grupo','Cidade/ATC','Município/UF para conferência','Funcionário','Fornecimento','Execução',
                         'Data original','Data da projeção','Classe de data','Erros salvos','Avisos salvos','Divergências de integridade',
                         'Justificativa de exclusão registrada','Faturas Impressas','Fatura Retida','Causa','Quantidade de comunicados','CO1 Atual',*KEYS,'Total oficial (centavos)',
                         *['Justificativa '+k for k in KEYS]]
                details=Sheets(book,'Registros',headers);bad_dates=Sheets(book,'Datas a conferir',headers)
                not_counted=Sheets(book,'Não contabilizados',headers)
                fee_rows=Sheets(book,'Feriados',['ID','Arquivo','Linha original','Ativo','Grupo','Município/UF','Cidade/ATC','Funcionário',
                    'Fornecimento','Execução','Data original','Data da projeção','Classe de data','Faturas Impressas','Fatura Retida','Causa',
                    'Quantidade cobrada','Valor (centavos)','Motivo','Erros salvos'])
                issues=Counter();date_counts=Counter();fee_reasons=Counter();official=Counter();saved=Counter();reevaluated=Counter();batch=[]
                holiday_days={r[0] for r in c.execute('SELECT DISTINCT day FROM holidays WHERE day LIKE ? OR day IN (SELECT day FROM record_metrics WHERE month=?)',(month+'-%',month))}
                review,review_args=holiday_review.review_sql(c,month)
                query='''SELECT r.*,i.name,i.mapping,m.id metric_id,m.day,m.employee,m.city,m.group_name,m.business_key,
                    m.excluded metric_excluded,m.import_deleted metric_deleted,'''+','.join('m.'+v for v in METRICS.values())+''',
                    h.charged,h.reason review_reason,h.municipality review_municipality,h.state review_state,
                    b.municipality bound_municipality,b.state bound_state,
                    p.id identity_id,p.supply identity_supply,p.execution identity_execution,p.source identity_source,p.eligible identity_eligible
                    FROM records r LEFT JOIN imports i ON i.id=r.import_id
                    LEFT JOIN record_metrics m ON m.id=r.id LEFT JOIN ('''+review+''') h ON h.id=r.id
                    LEFT JOIN holiday_identity_records p ON p.id=r.id LEFT JOIN municipality_bindings b ON b.source=p.source
                    WHERE r.month=? ORDER BY r.id'''
                for n,row in enumerate(c.execute(query,[*review_args,month]),1):
                    raw=json.loads(row['raw']);result=json.loads(row['result']);mapping=json.loads(row['mapping']) if row['mapping'] else {}
                    active=not(row['excluded'] or row['import_deleted']);metric_active=not(row['metric_excluded'] or row['metric_deleted']) and row['metric_id'] is not None
                    units={k:row[v] or 0 if metric_active else 0 for k,v in METRICS.items()}
                    units['feriado']=int(row['charged'] or 0)
                    engine=core.evaluate(raw,mapping,month);problems=[]
                    town,state,_,_=localities.resolve(row['city'])
                    if row['bound_municipality'] or row['bound_state']:town,state=row['bound_municipality'],row['bound_state']
                    if row['review_municipality'] or row['review_state']:town,state=row['review_municipality'],row['review_state']
                    geo=(town or 'Município não confirmado')+'/'+(state or 'UF não confirmada')
                    if row['mapping'] is None:problems.append('Importação de origem ausente')
                    if row['metric_id'] is not None and any(not isinstance(row[v],int) for v in METRICS.values()):problems.append('Unidades SQL não inteiras')
                    if core.fingerprint(raw)!=row['fingerprint']:problems.append('Fingerprint diferente dos dados armazenados')
                    if row['metric_id'] is None:problems.append('Projeção SQL ausente')
                    if row['identity_id'] is None:problems.append('Identidade do adicional ausente')
                    elif row['mapping'] and [row['identity_supply'],row['identity_execution'],row['identity_source'],row['identity_eligible']]!=json.loads(holidays.identity(row['raw'],row['mapping'])):
                        problems.append('Identidade do adicional diferente dos dados originais')
                    if result['units']!=engine['units']:problems.append('Motor atual diferente do resultado salvo')
                    if row['metric_id'] is not None and any(row[v]!=result['units'][k] for k,v in METRICS.items()):problems.append('Unidades SQL diferentes do resultado salvo')
                    if row['metric_id'] is not None and (row['excluded']!=row['metric_excluded'] or row['import_deleted']!=row['metric_deleted']):problems.append('Flags de exclusão divergentes')
                    dc=date_class(raw,mapping,month);date_counts[dc]+=1
                    parsed=periods.parse_date(raw.get(mapping.get('date')))
                    if (parsed.isoformat() if parsed else None)!=row['day']:problems.append('Data da projeção diferente da interpretação atual')
                    for problem in problems:issues[problem]+=1
                    for k in core.CATEGORIES:
                        saved[k]+=result['units'][k] if active else 0;reevaluated[k]+=engine['units'][k] if active else 0
                    official.update(units);total=sum(units[k]*prices[k] for k in KEYS)
                    reasons=row_reasons(raw,mapping,result,units,active);reasons['feriado']=holiday_reason(row,raw,mapping,holiday_days)
                    fee_reasons[reasons['feriado']]+=1
                    entry=[row['id'],row['import_id'],row['name'],row['line'],active,row['group_name'],row['city'],geo,row['employee'],raw.get(mapping.get('supply')),raw.get(mapping.get('task')),
                           raw.get(mapping.get('date')),row['day'],dc,'; '.join(result['errors']),'; '.join(result['alerts']),'; '.join(problems),
                           row['reason'],*[raw.get(mapping.get(k)) for k in ('printed','retained','cause','copies','operational')],
                           *[units[k] for k in KEYS],total,*[reasons[k] for k in KEYS]]
                    details.append(entry)
                    if dc!='Data válida no mês' or row['day'] is None:bad_dates.append(entry)
                    if not active or result['errors'] or total==0 or problems:not_counted.append(entry)
                    fee_rows.append([row['id'],row['name'],row['line'],active,row['group_name'],geo,row['city'],row['employee'],
                        raw.get(mapping.get('supply')),raw.get(mapping.get('task')),raw.get(mapping.get('date')),row['day'],dc,
                        raw.get(mapping.get('printed')),raw.get(mapping.get('retained')),raw.get(mapping.get('cause')),
                        units['feriado'],units['feriado']*105,reasons['feriado'],'; '.join(result['errors'])])
                    canonical='|'.join(str(x) for x in (raw.get(mapping.get('supply')),row['day'],raw.get(mapping.get('task')))) if row['day'] and raw.get(mapping.get('supply')) and raw.get(mapping.get('task')) else None
                    batch.append((row['id'],row['import_id'],row['line'],row['fingerprint'],int(active),row['group_name'],row['city'],geo,row['employee'],row['day'],dc,row['business_key'],canonical,
                                  *[units[k] for k in KEYS],total))
                    if len(batch)>=1000:scratch.executemany('INSERT INTO rows VALUES('+','.join('?'*20)+')',batch);batch=[];print(f'{n} registros conferidos',flush=True)
                if batch:scratch.executemany('INSERT INTO rows VALUES('+','.join('?'*20)+')',batch)
                scratch.executescript('CREATE INDEX fp ON rows(fp);CREATE INDEX import_fp ON rows(import_id,fp);CREATE INDEX business ON rows(business);CREATE INDEX execution_key ON rows(execution_key);')
                scratch.commit()
                sql_units=c.execute('SELECT '+','.join(f'COALESCE(SUM({v}),0) "{k}"' for k,v in METRICS.items())+
                    ' FROM record_metrics WHERE month=? AND excluded=0 AND import_deleted=0',(month,)).fetchone()
                report.update(official_quantities=dict(sql_units)|{'feriado':official['feriado']},
                              detail_quantities={k:official[k] for k in KEYS},
                              saved_five_quantities=dict(saved),reevaluated_five_quantities=dict(reevaluated),date_classes=dict(date_counts),integrity_issues=dict(issues),holiday_reasons=dict(fee_reasons))
                charge_sql,charge_args=holidays.charges_query(c,month)
                report['holiday_charged_sql']=c.execute('SELECT COUNT(*) FROM ('+charge_sql+')',charge_args).fetchone()[0]
                report['holiday_quantity_matches_sql']=report['holiday_charged_sql']==official['feriado']
                report['official_quantities']['feriado']=report['holiday_charged_sql']
                report['official_total_cents']=sum(report['official_quantities'][k]*prices[k] for k in KEYS)
                report['official_total_matches_reported']=report['official_total_cents']==report['claimed_app_cents']
                report['prices_match_informed']=prices==PRICES
                report['detail_quantities_match_sql']=report['official_quantities']==report['detail_quantities']
                report['orphan_metrics']=c.execute('SELECT COUNT(*) FROM record_metrics m LEFT JOIN records r ON r.id=m.id WHERE m.month=? AND r.id IS NULL',(month,)).fetchone()[0]
                if report['orphan_metrics']:report['integrity_issues']['Projeções SQL sem registro original']=report['orphan_metrics']
                report['all_records']=scratch.execute('SELECT COUNT(*) FROM rows').fetchone()[0]
                report['active_records']=scratch.execute('SELECT COUNT(*) FROM rows WHERE active=1').fetchone()[0]
                report['all_missing_projected_date']=c.execute('SELECT COUNT(*) FROM record_metrics WHERE month=? AND day IS NULL',(month,)).fetchone()[0]
                report['active_missing_projected_date']=c.execute('SELECT COUNT(*) FROM record_metrics WHERE month=? AND day IS NULL AND excluded=0 AND import_deleted=0',(month,)).fetchone()[0]
                report['comparison']=comparison(report['official_quantities'],prices)
                for field,title in [('grp','Por grupo'),('geo','Por município UF'),('city','Por cidade ATC'),('employee','Por funcionário'),('day','Por data'),('date_class','Por classe de data')]:
                    sheet=Sheets(book,title,['Dimensão','Registros','Ativos',*KEYS,'Total (centavos)'])
                    for r in scratch.execute('SELECT '+field+',COUNT(*),SUM(active),SUM(u138),SUM(u128),SUM(u137),SUM(uprint),SUM(uop),SUM(fee),SUM(total) FROM rows GROUP BY '+field+' ORDER BY '+field):sheet.append(list(r))
                sheet=Sheets(book,'Grupo município funcionário',['Grupo','Município/UF','Funcionário','Data','Registros',*KEYS,'Total (centavos)'])
                for r in scratch.execute('SELECT grp,geo,employee,day,COUNT(*),SUM(u138),SUM(u128),SUM(u137),SUM(uprint),SUM(uop),SUM(fee),SUM(total) FROM rows GROUP BY grp,geo,employee,day'):sheet.append(list(r))
                dup=Sheets(book,'Duplicidades',['Tipo','Chave','Registros'])
                dup_ids=Sheets(book,'IDs duplicidades',['Tipo','Chave','ID','Importação','Linha original'])
                for field,label in [('fp','Fingerprint ativo'),('business','Chave de negócio ativa'),('execution_key','Fornecimento/data/execução ativa')]:
                    count=0
                    for r in scratch.execute('SELECT '+field+',COUNT(*) FROM rows WHERE active=1 AND '+field+' IS NOT NULL GROUP BY '+field+' HAVING COUNT(*)>1'):
                        count+=1;dup.append([label,*r])
                    for r in scratch.execute('SELECT '+field+',id,import_id,line FROM rows WHERE active=1 AND '+field+' IN (SELECT '+field+' FROM rows WHERE active=1 AND '+field+' IS NOT NULL GROUP BY '+field+' HAVING COUNT(*)>1) ORDER BY '+field+',id'):
                        dup_ids.append([label,*r])
                    report[label]=count
                imports=[dict(r) for r in c.execute('SELECT * FROM imports WHERE month=? ORDER BY id',(month,))]
                ignored=Sheets(book,'Originais e ignorados',['Importação','Arquivo','Linha original','Fingerprint','Classificação comprovável','ID encontrado','Importação dona atualmente'])
                group_count=scratch.execute('SELECT COUNT(DISTINCT grp) FROM rows WHERE active=1').fetchone()[0]
                groups=[r[0] for r in scratch.execute('SELECT DISTINCT grp FROM rows WHERE active=1 LIMIT 1000')]
                report['active_groups']=groups
                report['active_group_count']=group_count
                present=set()
                for value in groups:
                    match=re.fullmatch(r'\s*(?:grupo\s*)?0?([1-9]|1[0-9]|20)\s*',str(value),re.I)
                    if match:present.add(int(match.group(1)))
                report['missing_group_labels_01_to_20']=sorted(set(range(1,21))-present)
                report['group_label_limit']=1000
                for imp in imports:
                    item={k:imp[k] for k in ('id','name','sheet','sha','deleted','created_at')}
                    item['stored_records']=scratch.execute('SELECT COUNT(*) FROM rows WHERE import_id=?',(imp['id'],)).fetchone()[0]
                    logs=[]
                    for a in c.execute("SELECT detail FROM audit WHERE month=? AND action='Importação' ORDER BY id",(month,)):
                        d=json.loads(a['detail'])
                        if d.get('sha256')==imp['sha'] and d.get('arquivo')==imp['name']:logs.append(d)
                    item['import_events']=logs
                    if check_originals:
                        item['source_rows']=0;counts=Counter()
                        try:
                            if not re.fullmatch('[0-9a-f]{64}',imp['sha']):raise ValueError('SHA de arquivo não reconhecido')
                            original=data/'originais'/(imp['sha']+'.xlsx');content=original.read_bytes()
                            item['sha_matches']=hashlib.sha256(content).hexdigest()==imp['sha']
                            if not item['sha_matches']:raise ValueError('Original difere do SHA arquivado')
                            parsed=next(p for p in excel_io.inspect(content) if p['sheet']==imp['sheet'])
                            item['headers_match']=parsed['headers']==json.loads(imp['headers'])
                            print('Conferindo original:',imp['name'],imp['sheet'],flush=True)
                            for row in excel_io.iter_records(content,parsed):
                                item['source_rows']+=1;fp=core.fingerprint(row['raw'])
                                repeated=scratch.execute('INSERT OR IGNORE INTO original_seen VALUES(?,?,?)',(imp['id'],fp,row['line'])).rowcount==0
                                owner=scratch.execute('SELECT id,import_id FROM rows WHERE import_id=? AND fp=? LIMIT 1',(imp['id'],fp)).fetchone()
                                other=scratch.execute('SELECT id,import_id FROM rows WHERE fp=? AND active=1 LIMIT 1',(fp,)).fetchone() if owner is None else None
                                label='Repetição idêntica dentro do original' if repeated else 'Preservado nessa importação' if owner else 'Mesmo fingerprint ativo em outro arquivo (estado atual)' if other else 'Sem registro correspondente no mês (investigar histórico)'
                                counts[label]+=1
                                if repeated or owner is None:ignored.append([imp['id'],imp['name'],row['line'],fp,label,owner[0] if owner else other[0] if other else None,owner[1] if owner else other[1] if other else None])
                            scratch.commit();item['source_classifications']=dict(counts)
                            if len(logs)==1:
                                item['source_rows_match_import_event']=item['source_rows']==logs[0].get('inseridos',0)+logs[0].get('duplicados_ignorados',0)
                        except Exception as e:item['original_error']=str(e)
                    report['imports'].append(item)
                report['originals_checked']=check_originals
                report['originals_verified']=bool(imports) and check_originals and all(x.get('sha_matches') and x.get('headers_match') and not x.get('original_error') for x in report['imports'])
                fee_summary=Sheets(book,'Resumo feriados motivos',['Motivo','Registros'])
                for reason,count in fee_reasons.most_common():fee_summary.append([reason,count])
                calendar=Sheets(book,'Calendário usado',['ID','Data','Descrição','Abrangência','UF','Município'])
                for row in c.execute('SELECT * FROM holidays WHERE day LIKE ? OR day IN (SELECT day FROM record_metrics WHERE month=?) ORDER BY day,id',(month+'-%',month)):calendar.append(list(row))
                history=Sheets(book,'Histórico existente',['ID','Mês','Ação','Detalhe original','Data UTC'])
                for row in c.execute('SELECT * FROM audit WHERE month=? OR month IS NULL ORDER BY id',(month,)):history.append(list(row))
                report['holiday_snapshot_frozen']=bool(c.execute('SELECT 1 FROM holiday_freeze WHERE month=?',(month,)).fetchone())
                report['proven']+=['Quantidades auditadas calculadas das projeções/IDs efetivamente usados pelo aplicativo, na transação de leitura.',
                                  'Valores salvos e motor atual comparados por registro; divergências relatadas sem corrigi-las.']
                report['limitations']=['Não há lista manual individual: a ferramenta não escolhe quais quatro feriados deveriam ser acrescentados.',
                    '20 arquivos não comprovam 20 grupos completos. Compare grupos ativos, linhas dos originais, hashes e eventos.',
                    'Sem registro de linhas ignoradas no banco, fingerprints dos originais comprovam correspondências atuais, não toda a decisão histórica.',
                    'Execuções repetidas são indícios para conferência; não são excluídas nem consideradas erros automaticamente.']
        else:
            report['proven'].append('A referência solicitada não existe nesse banco; fechamento real não foi auditado.')
        print('Conferindo integridade SQLite…',flush=True)
        report['sqlite_integrity_check']=c.execute('PRAGMA integrity_check').fetchone()[0]
    comp=report['comparison'];sheet=Sheets(book,'Comparação',list(comp[0]))
    for row in comp:sheet.append(list(row.values()))
    meta=Sheets(book,'Evidências e limites',['Tipo','Descrição'])
    for typ in ('proven','hypotheses','limitations'):
        for text in report.get(typ,[]):meta.append([typ,text])
    imports=Sheets(book,'Importações',['ID','Arquivo','Aba','Excluído','Registros salvos','Linhas original','SHA confere','Erro','Eventos','Classificações originais'])
    for row in report['imports']:imports.append([row['id'],row['name'],row['sheet'],row['deleted'],row['stored_records'],row.get('source_rows'),row.get('sha_matches'),row.get('original_error'),json.dumps(row['import_events'],ensure_ascii=False),json.dumps(row.get('source_classifications'),ensure_ascii=False)])
    book.save(output/'auditoria.xlsx')
    (output/'resultado.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    text=f'# Auditoria {month}\n\nBase real disponível: {report["available"]}. Auditoria somente leitura.\n\n'
    text+='| Serviço | Manual informado | App informado | Diferença | Valor da diferença |\n| --- | ---: | ---: | ---: | ---: |\n'
    for row in comparison():
        value=f'{row["Diferença informada (centavos)"]/100:.2f}'.replace('.',',')
        text+=f'| {row["Categoria"]} | {row["Manual informado"]} | {row["Aplicativo informado"]} | {row["Diferença informada"]} | R$ {value} |\n'
    text+='\nDiferença informada total: R$ 1.400,98. Comprovada aritmeticamente; causa ainda depende dos registros.\n\n'
    for typ,label in [('proven','Comprovado nesta execução'),('hypotheses','Hipóteses'),('limitations','Limitações')]:
        text+='## '+label+'\n\n'+''.join('- '+s+'\n' for s in report.get(typ,[]))+'\n'
    if report['available']:text+='## Resultado da base\n\n```json\n'+json.dumps({k:report[k] for k in ['official_total_cents','official_quantities','date_classes','all_missing_projected_date','active_missing_projected_date','integrity_issues','active_groups']},ensure_ascii=False,indent=2)+'\n```\n'
    text+='\nConfira auditoria.xlsx e resultado.json. Nada foi resolvido automaticamente.\n'
    (output/'RELATORIO.md').write_text(text,encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',default='data');p.add_argument('--month',default='2026-09',choices=['2026-09']);p.add_argument('--output',required=True)
    p.add_argument('--sem-originais',action='store_true',help='Não relê arquivos Excel; reduz a cobertura da conferência de importação.')
    args=p.parse_args();result=audit(args.data,args.output,args.month,not args.sem_originais)
    print(f'Auditoria concluída em {args.output}. Base de setembro disponível: {result["available"]}. Nenhum dado alterado.',flush=True)
