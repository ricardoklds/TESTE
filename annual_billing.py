"""Faturamento anual: leitura dos totais existentes, sem migrações financeiras."""
from contextlib import contextmanager,closing,ExitStack
from pathlib import Path
from datetime import date,datetime,timezone
from decimal import Decimal,ROUND_HALF_UP
import sqlite3,json,os,uuid

DEFAULT_TARGET=65000000
BANKS=('contrato.sqlite3','vistorias/financeiro.sqlite3','vistorias/vistorias.sqlite3','contrato_geral/consolidacao.sqlite3')

def shift(month,offset):
    d=date.fromisoformat(month+'-01');n=d.year*12+d.month-1+offset
    return f'{n//12:04d}-{n%12+1:02d}'

def version(data,include_goals=True):
    # WAL também muda antes de um checkpoint. Não abre nem cria banco.
    paths=[Path(data)/n for n in BANKS]
    if include_goals:paths.append(Path(data)/'gerencial/metas_anuais.json')
    return tuple((str(p),p.stat().st_mtime_ns,p.stat().st_size) if p.exists() else (str(p),None,None) for base in paths for p in (base,Path(str(base)+'-wal')))

@contextmanager
def readonly(path):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as c:
        c.row_factory=sqlite3.Row;c.execute('PRAGMA query_only=ON');c.execute('BEGIN');yield c

def goals(data):
    p=Path(data)/'gerencial/metas_anuais.json'
    if not p.exists():return []
    value=json.loads(p.read_text(encoding='utf-8'))
    if value.get('version')!=1:raise ValueError('Histórico de metas desconhecido; arquivo preservado.')
    return value['history']

def save_goal(data,effective,amount):
    date.fromisoformat(effective+'-01');d=Decimal(str(amount))
    if not d.is_finite() or d<=0 or d*100!=(d*100).to_integral_value():raise ValueError('Meta deve ser positiva, com até duas casas decimais.')
    folder=Path(data)/'gerencial';folder.mkdir(parents=True,exist_ok=True);lock=folder/'metas_anuais.lock'
    try:fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:raise ValueError('Outra gravação de meta está em andamento. Tente novamente.')
    tmp=folder/('metas-'+uuid.uuid4().hex+'.tmp')
    try:
        history=goals(data);history.append({'effective':effective,'cents':int(d*100),'created':datetime.now(timezone.utc).isoformat(),'id':uuid.uuid4().hex})
        with tmp.open('x',encoding='utf-8') as f:
            json.dump({'version':1,'history':history},f,ensure_ascii=False,indent=2);f.flush();os.fsync(f.fileno())
        os.replace(tmp,folder/'metas_anuais.json')
    finally:
        os.close(fd);lock.unlink()
        if tmp.exists():tmp.unlink()

def target(history,month):
    matches=[(r['effective'],i,r['cents']) for i,r in enumerate(history) if r['effective']<=month]
    return max(matches)[2] if matches else DEFAULT_TARGET

def monthly(data,start,end):
    """Busca somente competências com dados; fotografias aprovadas têm prioridade."""
    import contract_finance as contract
    import inspection_billing as visits
    data=Path(data);out={}
    with ExitStack() as stack:
        banks={n:stack.enter_context(readonly(data/n)) for n in BANKS if (data/n).exists()}
        general=banks.get(BANKS[3]);read=banks.get(BANKS[0]);fin=banks.get(BANKS[1]);op=banks.get(BANKS[2])
        snapshots={r['month']:json.loads(r['payload']) for r in general.execute('SELECT month,payload FROM closings WHERE month BETWEEN ? AND ?',(start,end))} if general else {}
        reads={r[0] for r in read.execute('SELECT month FROM imports WHERE deleted=0 AND month BETWEEN ? AND ? GROUP BY month',(start,end))} if read else set()
        if read:reads.update(r[0] for r in read.execute('SELECT month FROM months WHERE closed=1 AND month BETWEEN ? AND ?',(start,end)))
        approved={r['month']:json.loads(r['payload']) for r in fin.execute('SELECT month,payload FROM approvals WHERE month BETWEEN ? AND ?',(start,end))} if fin else {}
        operational={r[0] for r in op.execute("SELECT substr(day,1,7) FROM visits WHERE day>=? AND day<? GROUP BY 1",(start+'-01',shift(end,1)+'-01'))} if op else set()
        visit_months=set(approved)|operational
        if fin:
            visit_months.update(r[0] for r in fin.execute('SELECT month FROM geo WHERE month BETWEEN ? AND ?',(start,end)))
            visit_months.update(r[0] for r in fin.execute('SELECT month FROM commercial WHERE month BETWEEN ? AND ? GROUP BY month',(start,end)))
        for month in sorted(set(snapshots)|reads|visit_months):
            if month in snapshots:
                p=snapshots[month]
                out[month]={'month':month,'readings_cents':p['readings']['cents'],'visits_cents':p['visits']['inspection_cents'],'geo_cents':p['visits']['geo']['cents'],'gross_cents':p['gross_cents'],'complete':True,'approved':True,'status':'Aprovado','notes':''};continue
            r=contract.readings(data,month) if month in reads else None
            v=approved.get(month)
            if v is None and fin and month in visit_months:v=visits.preview(data/'vistorias',month,connection=fin)
            geo=v['geo']['cents'] if v and v['geo']['ready'] else None
            complete=bool(r is not None and v is not None and v['ready'] and geo is not None)
            notes=[]
            if r is None:notes.append('Sem dados de Leituras')
            if v is None:notes.append('Sem dados financeiros de Vistorias')
            elif not v['ready']:notes.append('Vistorias com pendências ou projeção incompleta')
            if geo is None:notes.append('Geolocalização não confirmada')
            a=r['cents'] if r else None;b=v['inspection_cents'] if v else None
            components_approved=bool(r and r['closed'] and month in approved)
            out[month]={'month':month,'readings_cents':a,'visits_cents':b,'geo_cents':geo,'gross_cents':sum(x for x in (a,b,geo) if x is not None) if any(x is not None for x in (a,b,geo)) else None,'complete':complete,'approved':False,'status':'Incompleto · provisório' if not complete else ('Componentes aprovados · Geral provisório' if components_approved else 'Provisório'),'notes':'; '.join(notes)}
    return out

def analyze(months,year,window,history=()):
    if window not in (3,6,12):raise ValueError('Média móvel deve ser de 3, 6 ou 12 meses.')
    rows=[]
    for n in range(1,13):
        month=f'{year:04d}-{n:02d}';r=dict(months.get(month,{'month':month,'readings_cents':None,'visits_cents':None,'geo_cents':None,'gross_cents':None,'complete':False,'approved':False,'status':'Sem dados','notes':''}))
        goal=target(history,month);gross=r['gross_cents'];period=[months.get(shift(month,-i)) for i in range(window)]
        full=all(p and p['complete'] and p['gross_cents'] is not None for p in period)
        avg=int((Decimal(sum(p['gross_cents'] for p in period))/window).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if full else None
        r.update(target_cents=goal,difference_cents=gross-goal if gross is not None else None,achievement=100*gross/goal if gross is not None else None,rolling_cents=avg,rolling_difference_cents=avg-goal if avg is not None else None,rolling_status=('Apenas aprovados' if all(p['approved'] for p in period) else 'Inclui provisórios') if full else 'Histórico insuficiente (competências consecutivas completas necessárias)')
        previous=months.get(shift(month,-1));r['previous_difference_cents']=gross-previous['gross_cents'] if r['complete'] and previous and previous['complete'] else None
        rows.append(r)
    available=[r for r in rows if r['gross_cents'] is not None];complete=[r for r in available if r['complete']]
    return {'year':year,'window':window,'rows':rows,'accumulated_cents':sum(r['gross_cents'] for r in available),'approved_cents':sum(r['gross_cents'] for r in available if r['approved']),'provisional_cents':sum(r['gross_cents'] for r in available if not r['approved']),'average_cents':int((Decimal(sum(r['gross_cents'] for r in complete))/len(complete)).quantize(Decimal('1'),rounding=ROUND_HALF_UP)) if complete else None,'best':max(complete,key=lambda r:r['gross_cents']) if complete else None,'worst':min(complete,key=lambda r:r['gross_cents']) if complete else None,'current':next((r for r in reversed(rows) if r['status']!='Sem dados'),None)}
