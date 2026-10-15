"""Consolidação mensal. Leituras consultadas exclusivamente em conexão somente leitura."""
from pathlib import Path
from contextlib import closing
import json,sqlite3
from decimal import Decimal,ROUND_HALF_UP
import inspection_billing as billing
import inspections

def connect(data):
    root=Path(data)/'contrato_geral';root.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(root/'consolidacao.sqlite3',factory=inspections.ClosingConnection);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000')
    if c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='audit'").fetchone():return c
    c.executescript('''CREATE TABLE IF NOT EXISTS closings(month TEXT PRIMARY KEY,payload TEXT NOT NULL,created TEXT NOT NULL,evidence TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS deductions(month TEXT PRIMARY KEY,payload TEXT NOT NULL,created TEXT NOT NULL,evidence TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,created TEXT NOT NULL,action TEXT NOT NULL,payload TEXT NOT NULL);''')
    return c

def readings(data,month):
    import managerial
    bank=Path(data).resolve()/'contrato.sqlite3'
    if not bank.exists():return {'cents':0,'closed':False,'revision':None,'reason':'Sem banco de leituras.'}
    with closing(managerial.connect(data)) as c:
        row=c.execute('SELECT prices,closed FROM months WHERE month=?',(month,)).fetchone()
        if row:prices=json.loads(row['prices'])
        else:
            import core
            setting=c.execute("SELECT value FROM settings WHERE key='prices'").fetchone()
            prices=json.loads(setting[0]) if setting else {k:v[2] for k,v in core.CATEGORIES.items()}
        sql,args=managerial.aggregate_sql(c,month)
        total=managerial.decorate(c.execute(sql,args).fetchone(),prices)
        revision=c.execute('SELECT revision FROM cache_revision WHERE id=1').fetchone()[0]
        return {'cents':total['total_cents'],'closed':bool(row and row['closed']),'revision':revision,'holiday_quantity':total['fee'],'units':{k:total[col] for k,col in managerial.UNITS.items()}}

def preview(data,month):
    read=readings(data,month);v=billing.financial(Path(data)/'vistorias',month)
    return {'month':month,'readings':read,'visits':v,'gross_cents':read['cents']+v['inspection_cents']+v['geo']['cents'],'ready':read['closed'] and v['approved']}

def state(data,month):
    with connect(data) as c:
        row=c.execute('SELECT payload FROM closings WHERE month=?',(month,)).fetchone();ded=c.execute('SELECT payload FROM deductions WHERE month=?',(month,)).fetchone()
    value=json.loads(row[0]) if row else preview(data,month)
    value['validated']=bool(row);value['deduction']=json.loads(ded[0]) if ded else None
    value['net_cents']=value['gross_cents']-(value['deduction']['cents'] if ded else 0);return value

def approve(data,month,expected,evidence,confirmed=False):
    if not confirmed or not evidence.strip():raise ValueError('Confirmação e documento obrigatórios.')
    with connect(data) as c:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('SELECT 1 FROM closings WHERE month=?',(month,)).fetchone():raise ValueError('Contrato já validado; versão anterior preservada.')
        p=preview(data,month)
        if billing.digest(p)!=expected or not p['ready']:raise ValueError('Base alterada ou incompleta: feche Leituras e aprove Vistorias/Geolocalização antes de validar o contrato.')
        # Fotografia do desempenho torna auditável a base usada na eventual glosa.
        first,last=billing.month_bounds(month);total,_,pending=inspections.summary(Path(data)/'vistorias',first,last)
        p['deadline']={**total,'pending':pending}
        c.execute('INSERT INTO closings VALUES(?,?,?,?)',(month,json.dumps(p,ensure_ascii=False),billing.now(),evidence))
        c.execute('INSERT INTO audit(created,action,payload) VALUES(?,?,?)',(billing.now(),'Validar contrato',json.dumps({'month':month,'snapshot':p,'evidence':evidence},ensure_ascii=False)))
    return p

def apply_fine(data,month,expected,evidence,confirmed=False):
    if not confirmed or not evidence.strip():raise ValueError('Confirmação explícita e justificativa obrigatórias.')
    with connect(data) as c:
        c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT payload FROM closings WHERE month=?',(month,)).fetchone()
        if not row:raise ValueError('Fechamento Geral ainda não validado.')
        p=json.loads(row[0]);deadline=p['deadline']
        if billing.digest(p)!=expected:raise ValueError('Base divergente da confirmação.')
        if deadline['pending'] or not deadline['total'] or deadline['met']:raise ValueError('Sem índice elegível para glosa.')
        if c.execute('SELECT 1 FROM deductions WHERE month=?',(month,)).fetchone():raise ValueError('Glosa já aplicada nesta competência.')
        cents=int((Decimal(p['gross_cents'])/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
        result={'month':month,'gross_cents':p['gross_cents'],'rate_percent':1,'cents':cents,'net_cents':p['gross_cents']-cents,'deadline':deadline,'closing_fingerprint':expected}
        c.execute('INSERT INTO deductions VALUES(?,?,?,?)',(month,json.dumps(result,ensure_ascii=False),billing.now(),evidence));c.execute('INSERT INTO audit(created,action,payload) VALUES(?,?,?)',(billing.now(),'Aplicar glosa',json.dumps({'result':result,'evidence':evidence},ensure_ascii=False)))
    return result
