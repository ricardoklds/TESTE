"""Finanças de vistorias em banco separado. Sem dependência das regras de leituras."""
from contextlib import closing
from datetime import datetime, date, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import calendar, hashlib, json, sqlite3, unicodedata, uuid
import inspections

SERVICES=(('200014105','Vistoria para aprovação de ligação',2250),('200014106','Vistoria predial',2250),('200014104','Vistoria de atualização cadastral',1200),('geo','Geolocalização',1200))

def norm(value):return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',str(value or '')) if not unicodedata.combining(c)).upper().split())
def month_bounds(month):
    first=date.fromisoformat(month+'-01');return first.isoformat(),first.replace(day=calendar.monthrange(first.year,first.month)[1]).isoformat()
def now():return datetime.now(timezone.utc).isoformat()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

def backup(path):
    path=Path(path)
    if not path.exists():return None
    dest=path.parent/'backups';dest.mkdir(exist_ok=True);target=dest/(path.stem+'-antes-financeiro-'+uuid.uuid4().hex+'.sqlite3')
    with closing(sqlite3.connect(path.as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup inválido: operação cancelada.')
    return str(target)

def connect(root):
    root=Path(root).resolve();root.mkdir(parents=True,exist_ok=True);p=root/'financeiro.sqlite3'
    c=sqlite3.connect(p,factory=inspections.ClosingConnection);c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000')
    version=c.execute('PRAGMA user_version').fetchone()[0]
    if version not in (0,1):c.close();raise ValueError('Banco financeiro desconhecido; migração não autorizada.')
    if version==1 and c.execute("SELECT 1 FROM metadata WHERE key='catalog_initial'").fetchone():return c
    c.executescript('''CREATE TABLE IF NOT EXISTS revision(id INTEGER PRIMARY KEY CHECK(id=1),value INTEGER NOT NULL); INSERT OR IGNORE INTO revision VALUES(1,0);
    CREATE TABLE IF NOT EXISTS services(code TEXT PRIMARY KEY,name TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS prices(code TEXT NOT NULL,effective TEXT NOT NULL,cents INTEGER NOT NULL CHECK(cents>=0),active INTEGER NOT NULL,PRIMARY KEY(code,effective));
    CREATE TABLE IF NOT EXISTS rules(id INTEGER PRIMARY KEY,tss TEXT NOT NULL,cause TEXT NOT NULL DEFAULT '',form TEXT NOT NULL DEFAULT '',effective TEXT NOT NULL,code TEXT,decision TEXT NOT NULL,evidence TEXT NOT NULL,UNIQUE(tss,cause,form,effective));
    CREATE TABLE IF NOT EXISTS commercial(id INTEGER PRIMARY KEY,day TEXT,city TEXT NOT NULL,os TEXT NOT NULL,contract TEXT NOT NULL,tss TEXT NOT NULL,cause TEXT NOT NULL,form TEXT NOT NULL,family TEXT NOT NULL,closed INTEGER NOT NULL,inactive INTEGER NOT NULL,raw_hash TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS commercial_period ON commercial(day,closed,tss);
    CREATE INDEX IF NOT EXISTS commercial_os ON commercial(contract,os);
    CREATE TABLE IF NOT EXISTS reviews(visit_id INTEGER NOT NULL,month TEXT NOT NULL,decision TEXT NOT NULL,code TEXT,evidence TEXT NOT NULL,PRIMARY KEY(visit_id,month));
    CREATE TABLE IF NOT EXISTS geo(month TEXT PRIMARY KEY,mode TEXT NOT NULL,total INTEGER,cities TEXT NOT NULL,evidence TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS approvals(month TEXT PRIMARY KEY,payload TEXT NOT NULL,created TEXT NOT NULL,evidence TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,created TEXT NOT NULL,action TEXT NOT NULL,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    PRAGMA user_version=1;''')
    for code,name,cents in SERVICES:
        c.execute('INSERT OR IGNORE INTO services VALUES(?,?)',(code,name));c.execute('INSERT OR IGNORE INTO prices VALUES(?,?,?,1)',(code,'2026-09',cents))
    if not c.execute("SELECT 1 FROM metadata WHERE key='catalog_initial'").fetchone():
        from inspection_catalog import MAPPING,EXCLUDED
        evidence='Mapeamento inicial confirmado pelo usuário em 15/10/2026; sem inferência por cores ou similaridade.'
        for code,descriptions in MAPPING.items():
            for description in descriptions:c.execute('INSERT OR IGNORE INTO rules(tss,effective,code,decision,evidence) VALUES(?,?,?,?,?)',(norm(description),'2026-09',code,'Cobrar',evidence))
        for description in EXCLUDED:c.execute('INSERT OR IGNORE INTO rules(tss,effective,decision,evidence) VALUES(?,?,?,?)',(norm(description),'2026-09','Excluir',evidence))
        c.execute("INSERT INTO metadata VALUES('catalog_initial','1')")
        audit(c,'Catálogo inicial confirmado',{'evidence':evidence})
    c.commit();return c

def revision(root):
    with connect(root) as c:return c.execute('SELECT value FROM revision WHERE id=1').fetchone()[0]
def audit(c,action,payload):
    c.execute('INSERT INTO audit(created,action,payload) VALUES(?,?,?)',(now(),action,json.dumps(payload,ensure_ascii=False)))
    c.execute('UPDATE revision SET value=value+1 WHERE id=1')
def editable(c,month):
    month_bounds(month)
    if c.execute('SELECT 1 FROM approvals WHERE month=?',(month,)).fetchone():raise ValueError('Competência aprovada; histórico preservado.')
def future(c,effective):
    month_bounds(effective)
    if c.execute('SELECT 1 FROM approvals WHERE month>=? LIMIT 1',(effective,)).fetchone():raise ValueError('Vigência alcança competência já aprovada. Use mês posterior.')

def sync(root,progress=None):
    """Projeção incremental, explícita e transacional. Não modifica banco operacional."""
    root=Path(root).resolve();source=root/'vistorias.sqlite3'
    if not source.exists():return 0
    # Backup consistente antes de preparar o índice financeiro da base existente.
    with connect(root) as check:prepared=check.execute("SELECT 1 FROM metadata WHERE key='prepared'").fetchone()
    if not prepared:backup(source);backup(root/'financeiro.sqlite3')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)) as src,connect(root) as c:
        c.execute('BEGIN IMMEDIATE');last=c.execute('SELECT COALESCE(MAX(id),0) FROM commercial').fetchone()[0];n=0
        cursor=src.execute('SELECT id,day,city,os,raw FROM visits WHERE id>? ORDER BY id',(last,))
        while batch:=cursor.fetchmany(2000):
            values=[]
            for id,day,city,os,rawtext in batch:
                r=json.loads(rawtext);closed=all(norm(r.get(k))=='FECHADA' for k in ('Status da OS','Status da Operação'))
                values.append((id,day,city,os,norm(r.get('Contrato')),norm(r.get('TSS')),norm(r.get('Causa Resultado')),norm(r.get('Formulário de Baixa')),norm(r.get('Família')),int(closed),int(norm(r.get('TSS'))=='VISTORIA LIGACAO INATIVA SEM DEBITO'),hashlib.sha256(rawtext.encode()).hexdigest()))
            c.executemany('INSERT INTO commercial VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',values);n+=len(values)
            if progress:progress(n)
        c.execute("INSERT OR REPLACE INTO metadata VALUES('prepared','1')")
        if n:audit(c,'Atualizar projeção comercial',{'rows':n,'last_id':last})
    return n

def service_list(root,month):
    with connect(root) as c:return [dict(r) for r in c.execute('''SELECT s.code,s.name,p.effective,p.cents,p.active FROM services s JOIN prices p ON p.code=s.code
      WHERE p.effective=(SELECT MAX(x.effective) FROM prices x WHERE x.code=s.code AND x.effective<=?) ORDER BY s.code''',(month,))]

def save_service(root,code,name,effective,cents,active,evidence):
    code=code.strip()
    if not code or not name.strip() or type(cents)!=int or cents<0 or not evidence.strip():raise ValueError('Código contratual confirmado, descrição, preço e justificativa obrigatórios.')
    with connect(root) as c:
        c.execute('BEGIN IMMEDIATE');future(c,effective)
        existing=c.execute('SELECT name FROM services WHERE code=?',(code,)).fetchone()
        if existing and existing[0]!=name.strip():raise ValueError('Preserve a descrição do código existente; adicione outro serviço quando necessário.')
        before=c.execute('SELECT * FROM prices WHERE code=? AND effective=?',(code,effective)).fetchone()
        c.execute('INSERT OR IGNORE INTO services VALUES(?,?)',(code.strip(),name.strip()))
        c.execute('INSERT OR REPLACE INTO prices VALUES(?,?,?,?)',(code.strip(),effective,cents,int(active)))
        audit(c,'Preço/vigência',{'code':code,'name':name,'effective':effective,'cents':cents,'active':bool(active),'evidence':evidence,'before':dict(before) if before else None})

def save_rule(root,tss,cause,form,effective,decision,code,evidence):
    if decision not in ('Cobrar','Excluir') or not norm(tss) or not evidence.strip():raise ValueError('TSS, decisão e comprovação obrigatórios.')
    with connect(root) as c:
        c.execute('BEGIN IMMEDIATE');future(c,effective)
        if decision=='Cobrar' and (code=='geo' or not c.execute('SELECT 1 FROM services WHERE code=?',(code,)).fetchone()):raise ValueError('Serviço contratual de vistoria inválido.')
        payload={'tss':norm(tss),'cause':norm(cause),'form':norm(form),'effective':effective,'decision':decision,'code':code if decision=='Cobrar' else None,'evidence':evidence}
        before=c.execute('SELECT * FROM rules WHERE tss=? AND cause=? AND form=? AND effective=?',(payload['tss'],payload['cause'],payload['form'],effective)).fetchone()
        c.execute('INSERT OR REPLACE INTO rules(tss,cause,form,effective,code,decision,evidence) VALUES(:tss,:cause,:form,:effective,:code,:decision,:evidence)',payload)
        audit(c,'Classificação TSS',{**payload,'before':dict(before) if before else None})

def review(root,visit_id,month,decision,code,evidence):
    if decision not in ('Cobrar','Excluir') or not evidence.strip():raise ValueError('Decisão e justificativa obrigatórias.')
    first,last=month_bounds(month)
    with connect(root) as c:
        c.execute('BEGIN IMMEDIATE');editable(c,month)
        if not c.execute('SELECT 1 FROM commercial WHERE id=? AND day BETWEEN ? AND ?',(visit_id,first,last)).fetchone():raise ValueError('Registro não pertence ao mês informado.')
        if decision=='Cobrar' and (code=='geo' or not c.execute('SELECT 1 FROM services WHERE code=?',(code,)).fetchone()):raise ValueError('Serviço inválido.')
        before=c.execute('SELECT * FROM reviews WHERE visit_id=? AND month=?',(visit_id,month)).fetchone()
        c.execute('INSERT OR REPLACE INTO reviews VALUES(?,?,?,?,?)',(visit_id,month,decision,code if decision=='Cobrar' else None,evidence))
        audit(c,'Conferência individual',{'id':visit_id,'month':month,'decision':decision,'code':code,'evidence':evidence,'before':dict(before) if before else None})

def save_geo(root,month,mode,total,cities,evidence):
    if mode not in ('Total mensal','Por município') or not evidence.strip():raise ValueError('Modo e documento obrigatórios.')
    if total is not None and (type(total)!=int or total<0):raise ValueError('Quantidade total inválida.')
    if any(not k.strip() or type(v)!=int or v<0 for k,v in cities.items()):raise ValueError('Município e quantidades inteiras não negativas obrigatórios.')
    names=[norm(k) for k in cities]
    if len(names)!=len(set(names)):raise ValueError('Município repetido.')
    if (mode=='Total mensal' and total is None) or (mode=='Por município' and not cities):raise ValueError('Preencha o modo escolhido; informe zero explicitamente quando não houver serviço.')
    with connect(root) as c:
        c.execute('BEGIN IMMEDIATE');editable(c,month)
        before=c.execute('SELECT * FROM geo WHERE month=?',(month,)).fetchone()
        c.execute('INSERT OR REPLACE INTO geo VALUES(?,?,?,?,?)',(month,mode,total,json.dumps(cities,ensure_ascii=False),evidence))
        audit(c,'Geolocalização',{'month':month,'before':dict(before) if before else None,'mode':mode,'total':total,'cities':cities,'evidence':evidence})

def geo_summary(c,month,prices):
    r=c.execute('SELECT * FROM geo WHERE month=?',(month,)).fetchone()
    if not r:return {'quantity':0,'cents':0,'ready':False,'reason':'Geolocalização não confirmada (zero deve ser informado explicitamente).'}
    cities=json.loads(r['cities']);quantity=r['total'] if r['mode']=='Total mensal' else sum(cities.values())
    matches=r['total'] is None or not cities or r['total']==sum(cities.values())
    price=prices.get('geo');ready=matches and price is not None and bool(price['active'])
    return {'quantity':quantity,'unit_cents':price['cents'] if price else None,'cents':quantity*price['cents'] if price else 0,'ready':ready,'mode':r['mode'],'cities_total':sum(cities.values()) if cities else None,'reference_total':r['total'],'reason':'' if ready else 'Total e municípios divergem ou preço inativo/ausente.'}

# Todas as classificações em SQL; registros brutos são lidos só na projeção/importação e exportação solicitada.
def classified_sql(month):
    first,last=month_bounds(month)
    sql='''WITH applicable AS (SELECT * FROM rules r WHERE effective<=:month AND effective=(SELECT MAX(effective) FROM rules x WHERE x.tss=r.tss AND x.cause=r.cause AND x.form=r.form AND x.effective<=:month)),
    matches AS (SELECT v.id,r.code,r.decision,ROW_NUMBER() OVER(PARTITION BY v.id ORDER BY (r.cause<>'')+(r.form<>'') DESC,r.id DESC) priority,
      COUNT(*) OVER(PARTITION BY v.id,(r.cause<>'')+(r.form<>'')) ambiguity FROM commercial v JOIN applicable r ON r.tss=v.tss AND (r.cause='' OR r.cause=v.cause) AND (r.form='' OR r.form=v.form) WHERE v.day BETWEEN :first AND :last),
    repeated AS (SELECT contract,os FROM commercial WHERE day BETWEEN :first AND :last AND os<>'' GROUP BY contract,os HAVING COUNT(*)>1),
    priced AS (SELECT p.* FROM prices p WHERE effective=(SELECT MAX(effective) FROM prices x WHERE x.code=p.code AND x.effective<=:month)),
    chosen AS (SELECT v.*,COALESCE(rv.decision,m.decision) decision,COALESCE(rv.code,m.code) code,rv.visit_id reviewed,COALESCE(m.ambiguity,0) ambiguity,
      EXISTS(SELECT 1 FROM repeated d WHERE d.contract=v.contract AND d.os=v.os) duplicate
      FROM commercial v LEFT JOIN matches m ON m.id=v.id AND m.priority=1 LEFT JOIN reviews rv ON rv.visit_id=v.id AND rv.month=:month WHERE v.day BETWEEN :first AND :last),
    resolved AS (SELECT v.*,p.cents,p.active,CASE WHEN closed=0 THEN 'Não concluída'
      WHEN decision='Excluir' AND (reviewed IS NOT NULL OR ambiguity<=1) THEN 'Excluído por classificação confirmada'
      WHEN reviewed IS NULL AND duplicate THEN 'Pendente: OS repetida'
      WHEN reviewed IS NULL AND inactive THEN 'Pendente: ligação inativa'
      WHEN reviewed IS NULL AND ambiguity>1 THEN 'Pendente: regras ambíguas'
      WHEN os='' THEN 'Pendente: OS ausente'
      WHEN decision IS NULL THEN 'Pendente: serviço não mapeado'
      WHEN cents IS NULL OR active<>1 THEN 'Pendente: preço ausente ou serviço inativo'
      ELSE 'Faturável' END reason FROM chosen v LEFT JOIN priced p ON p.code=v.code)
    SELECT * FROM resolved'''
    return sql,{'month':month,'first':first,'last':last}

def preview(root,month,connection=None):
    if connection is None:
        with connect(root) as c:return preview(root,month,c)
    c=connection;sql,args=classified_sql(month)
    groups=[dict(r) for r in c.execute('SELECT reason,code,COUNT(*) quantity,COALESCE(SUM(CASE WHEN reason=\'Faturável\' THEN cents ELSE 0 END),0) cents FROM ('+sql+') GROUP BY reason,code',args)]
    # Todas as linhas sem data ficam pendentes globais: não atribuir mês por suposição.
    undated=c.execute('SELECT COUNT(*) FROM commercial WHERE day IS NULL AND closed=1').fetchone()[0]
    pending=sum(r['quantity'] for r in groups if r['reason'].startswith('Pendente:'))+undated
    services=service_list_connection(c,month);geo=geo_summary(c,month,services)
    projection_last=c.execute('SELECT COALESCE(MAX(id),0) FROM commercial').fetchone()[0]
    visits=Path(root)/'vistorias.sqlite3';actual_last=0
    if visits.exists():
        with closing(sqlite3.connect(visits.resolve().as_uri()+'?mode=ro',uri=True)) as op:actual_last=op.execute('SELECT COALESCE(MAX(id),0) FROM visits').fetchone()[0]
    ready=projection_last==actual_last and pending==0
    byservice=[{'code':code,'name':p['name'],'quantity':sum(r['quantity'] for r in groups if r['reason']=='Faturável' and r['code']==code),'cents':sum(r['cents'] for r in groups if r['reason']=='Faturável' and r['code']==code),'unit_cents':p['cents']} for code,p in services.items() if code!='geo']
    result={'month':month,'groups':groups,'services':byservice,'pending':pending,'undated':undated,'ready':ready,'sync_pending':actual_last-projection_last,'geo':geo,'inspection_cents':sum(r['cents'] for r in groups),'revision':c.execute('SELECT value FROM revision WHERE id=1').fetchone()[0]}
    result['fingerprint']=digest(result);return result

def service_list_connection(c,month):
    return {r['code']:dict(r) for r in c.execute('''SELECT s.code,s.name,p.* FROM services s JOIN prices p ON p.code=s.code WHERE p.effective=(SELECT MAX(effective) FROM prices x WHERE x.code=s.code AND x.effective<=?)''',(month,))}

def approve(root,month,expected,evidence,confirmed=False):
    if not confirmed or not evidence.strip():raise ValueError('Conciliação e confirmação explícita obrigatórias.')
    with connect(root) as c:
        c.execute('BEGIN IMMEDIATE');editable(c,month);p=preview(root,month,c)
        if p['fingerprint']!=expected:raise ValueError('Dados alterados; gere novamente a conciliação.')
        if not p['ready'] or not p['geo']['ready']:raise ValueError('Há pendências de classificação, sincronização ou geolocalização.')
        c.execute('INSERT INTO approvals VALUES(?,?,?,?)',(month,json.dumps(p,ensure_ascii=False),now(),evidence));audit(c,'Aprovar faturamento de vistorias',{'month':month,'snapshot':p,'evidence':evidence})
    return p

def financial(root,month):
    with connect(root) as c:
        r=c.execute('SELECT payload FROM approvals WHERE month=?',(month,)).fetchone()
        if r:return {**json.loads(r[0]),'approved':True}
    return {**preview(root,month),'approved':False}

def detail_page(root,month,offset=0,limit=50):
    if not 1<=limit<=100 or offset<0:raise ValueError('Paginação inválida.')
    sql,args=classified_sql(month);args.update(limit=limit,offset=offset)
    with connect(root) as c:return [dict(r) for r in c.execute('SELECT * FROM ('+sql+') ORDER BY id LIMIT :limit OFFSET :offset',args)]

def reconciliation(root,month,references=None,detail=False):
    """Referências são somente comparação, nunca participam da classificação."""
    from io import BytesIO
    import openpyxl
    from fast_reports import text_row
    p=preview(root,month);w=openpyxl.Workbook(write_only=True);s=w.create_sheet('Conciliação');text_row(s,['Código','Serviço','Calculado dos registros','Referência informada','Diferença','Valor apurado em centavos'])
    for r in p['services']:
        ref=(references or {}).get(r['code']);text_row(s,[r['code'],r['name'],r['quantity'],ref,r['quantity']-ref if ref is not None else None,r['cents']])
    s=w.create_sheet('Motivos');text_row(s,['Motivo','Código','Quantidade','Valor em centavos'])
    for r in p['groups']:text_row(s,[r['reason'],r['code'],r['quantity'],r['cents']])
    text_row(s,['Sem data de execução (globais)',None,p['undated'],0])
    s=w.create_sheet('Metadados');text_row(s,['Competência',month]);text_row(s,['Impressão digital da prévia',p['fingerprint']]);text_row(s,['Situação','Prévia; depende de aprovação explícita']);text_row(s,['Regra','OS e operação Fechada; competência por execução; sem dependência da tabela dinâmica. Referências não afetam cálculos.'])
    sql,args=classified_sql(month)
    s=w.create_sheet('Apuração por TSS');text_row(s,['TSS','Código','Motivo','Quantidade','Valor em centavos'])
    with connect(root) as c:
        for r in c.execute("SELECT tss,code,reason,COUNT(*),SUM(CASE WHEN reason='Faturável' THEN cents ELSE 0 END) FROM ("+sql+") GROUP BY tss,code,reason ORDER BY code,tss",args):text_row(s,list(r))
    if detail:
        sql,args=classified_sql(month)
        with connect(root) as c:
            n=0
            for r in c.execute(sql+' ORDER BY id',args):
                if n%1048575==0:
                    s=w.create_sheet('Registros '+str(1+n//1048575));text_row(s,['ID','OS','Data','Município','TSS','Causa','Formulário','Código','Motivo','Valor em centavos'])
                text_row(s,[r['id'],r['os'],r['day'],r['city'],r['tss'],r['cause'],r['form'],r['code'],r['reason'],r['cents'] if r['reason']=='Faturável' else 0]);n+=1
    b=BytesIO();w.save(b);return b.getvalue()

def export_catalog(root,month):
    """Configuração vigente para o recálculo independente, sem acessar Excel."""
    with connect(root) as c:
        rules=[dict(r) for r in c.execute('SELECT * FROM rules r WHERE effective=(SELECT MAX(effective) FROM rules x WHERE x.tss=r.tss AND x.cause=r.cause AND x.form=r.form AND effective<=?) AND r.effective<=?',(month,month))]
        reviews={r['raw_hash']:{'decision':r['decision'],'code':r['code']} for r in c.execute('SELECT v.raw_hash,r.decision,r.code FROM reviews r JOIN commercial v ON v.id=r.visit_id WHERE r.month=?',(month,))}
        return {'month':month,'prices':service_list_connection(c,month),'rules':rules,'reviews':reviews,'scope':'Catálogo e decisões exportados para '+month}
