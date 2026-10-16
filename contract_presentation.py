"""Composição e simulação de apresentação. Não grava nem aprova fechamentos."""
from decimal import Decimal,ROUND_HALF_UP
from contextlib import closing
from pathlib import Path
import json,sqlite3

def simulate(gross_cents,enabled,percent=1):
    rate=Decimal(str(percent))
    if not rate.is_finite() or not Decimal('0.1')<=rate<=5 or rate*10!=(rate*10).to_integral_value():
        raise ValueError('Percentual deve estar entre 0,1% e 5%, em passos de 0,1%.')
    deduction=int((Decimal(gross_cents)*rate/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if enabled else 0
    return {'gross_cents':gross_cents,'deduction_cents':deduction,'net_cents':gross_cents-deduction}

def legacy_readings(data,p):
    """Só preços pontuais de um mês fechado; nunca recalcula registros históricos."""
    import core,contract_finance
    r=p['readings'];units=r.get('units',{})
    if not all(k in units for k in [*core.CATEGORIES,'feriado']):return None
    bank=Path(data).resolve()/'contrato.sqlite3'
    if not bank.exists():return None
    with closing(sqlite3.connect(bank.as_uri()+'?mode=ro',uri=True)) as c:
        row=c.execute('SELECT prices,closed FROM months WHERE month=?',(p['month'],)).fetchone()
    if not row or not row[1] or not r.get('closed'):return None
    rows=contract_finance.reading_services(units,json.loads(row[0]))
    return rows if sum(s['cents'] for s in rows)==r['cents'] else None

def compose(data,p):
    import core
    notes=[];read=p['readings'];v=p['visits'];read_rows=read.get('services')
    if read_rows is None:read_rows=legacy_readings(data,p)
    complete=read_rows is not None
    if read_rows is None:
        descriptors=[(code,label) for code,label,_ in core.CATEGORIES.values()]+[('200014097','Adicional de leitura em feriado')]
        read_rows=[{'code':code,'name':name,'quantity':None,'unit_cents':None,'cents':None} for code,name in descriptors]
        notes.append('A fotografia histórica de Leituras não contém detalhamento comprovável. Total preservado; quantidades e preços indisponíveis não foram inventados.')
    rows=[{**r,'component':'Leituras','rate_details':[]} for r in read_rows]
    for r in v['services']:
        rates=[x for x in v.get('rates',[]) if x['code']==r['code']]
        rows.append({**r,'component':'Vistorias','rate_details':rates if r.get('unit_cents') is None else []})
    geo=v['geo'];rows.append({'component':'Geolocalização','code':'geo','name':'Geolocalização','quantity':geo['quantity'],'unit_cents':geo.get('unit_cents'),'cents':geo['cents'],'rate_details':[]})
    subtotals={'Leituras':read['cents'],'Vistorias':v['inspection_cents'],'Geolocalização':geo['cents']}
    for component,total in subtotals.items():
        group=[r for r in rows if r['component']==component]
        if all(r['cents'] is not None for r in group) and sum(r['cents'] for r in group)!=total:raise ValueError('Composição divergente do total de '+component+'. Indicadores preservados; confira a origem.')
    if sum(subtotals.values())!=p['gross_cents']:raise ValueError('Componentes não coincidem com o fechamento bruto.')
    if not read.get('closed'):notes.append('Leituras: fechamento ainda não aprovado/encerrado.')
    if not v.get('approved'):notes.append('Vistorias e Geolocalização: competência ainda não aprovada.')
    if v.get('pending'):notes.append(f"Vistorias: {v['pending']} pendências comerciais, incluindo datas globais quando informadas pelo sistema.")
    if v.get('sync_pending'):notes.append('Vistorias: projeção comercial pendente de atualização.')
    if not geo.get('ready'):notes.append('Geolocalização pendente: '+geo.get('reason','conferência necessária.'))
    notes.append('Quantidades são faturáveis por serviço. Adicionais podem se acumular sobre uma leitura; não representam fornecimentos distintos nem a quantidade de registros operacionais.')
    notes.append('Vistorias + Geolocalização é subtotal informativo; não é somado novamente ao faturamento bruto.')
    notes.append('Código geo é o identificador interno da Geolocalização; não há código contratual confirmado no cadastro.')
    return {'month':p['month'],'rows':rows,'subtotals':subtotals,'gross_cents':p['gross_cents'],'visits_geo_cents':subtotals['Vistorias']+subtotals['Geolocalização'],'notes':notes,'complete':complete}

def money(cents):
    if cents is None:return 'Não disponível'
    return f'R$ {cents/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')

def unit_text(row):
    if row.get('unit_cents') is not None:return money(row['unit_cents'])
    if row.get('rate_details'):return ' / '.join(f"{r['quantity']} × {money(r['unit_cents'])}" for r in row['rate_details'])
    return 'Não disponível'

def table_rows(composition):
    return [{'Componente':r['component'],'Código contratual':r['code'] if r['code']!='geo' else 'Não informado (geo)','Descrição':r['name'],'Quantidade faturável':r['quantity'],'Valor unitário':unit_text(r),'Valor total':money(r['cents'])} for r in composition['rows']]
