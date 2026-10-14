"""Adicional independente; nunca modifica os cinco resultados financeiros salvos."""
from contextlib import closing
from datetime import date
import json
import sqlite3
from uuid import uuid4
import core

UNIT=105
UFS={'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'}

def identity(raw,mapping):
    r=json.loads(raw);m=json.loads(mapping)
    get=lambda k:r.get(m.get(k))
    city=get('city')
    if not m.get('city'):
        aliases={'cidade/atc','cidade / atc','atc','cidade','municipio'}
        values={core.norm(value) for key,value in r.items() if core.norm(key) in aliases and core.norm(value)}
        city=next(iter(values)) if len(values)==1 else ('__colunas_municipais_divergentes__' if values else '')
    return json.dumps([str(get('supply') or '').strip(),str(get('task') or '').strip(),core.norm(city),
                       int(core.norm(get('retained'))=='nao' and not core.norm(get('cause')))],ensure_ascii=False)

def prepare(c,data):
    c.create_function('holiday_identity',2,identity,deterministic=True)
    if c.execute('PRAGMA user_version').fetchone()[0]>=4:return
    folder=data/'backups';folder.mkdir(exist_ok=True)
    with sqlite3.connect(folder/('antes-migracao-v4-'+uuid4().hex+'.sqlite3')) as backup:
        c.backup(backup)
        if backup.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup inválido; migração de feriados cancelada.')
    try:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('PRAGMA user_version').fetchone()[0]>=4:c.commit();return
        c.execute('CREATE TABLE holidays(id INTEGER PRIMARY KEY,day TEXT NOT NULL,description TEXT NOT NULL,scope TEXT NOT NULL,state TEXT NOT NULL,municipality TEXT NOT NULL,UNIQUE(day,scope,state,municipality))')
        c.execute('CREATE INDEX holidays_day ON holidays(day)')
        c.execute('CREATE TABLE municipality_bindings(source TEXT PRIMARY KEY,municipality TEXT NOT NULL,state TEXT NOT NULL)')
        c.execute('CREATE TABLE holiday_identity_records(id INTEGER PRIMARY KEY,supply TEXT,execution TEXT,source TEXT,eligible INTEGER)')
        projection='''SELECT r.id,json_extract(holiday_identity(r.raw,i.mapping),'$[0]'),
           json_extract(holiday_identity(r.raw,i.mapping),'$[1]'),json_extract(holiday_identity(r.raw,i.mapping),'$[2]'),
           json_extract(holiday_identity(r.raw,i.mapping),'$[3]') FROM records r JOIN imports i ON i.id=r.import_id'''
        c.execute('INSERT INTO holiday_identity_records '+projection)
        c.execute('CREATE INDEX holiday_identity_source ON holiday_identity_records(source,id)')
        c.execute('CREATE TABLE holiday_freeze(month TEXT PRIMARY KEY)')
        c.execute('CREATE TABLE holiday_frozen_records(month TEXT,id INTEGER,municipality TEXT,state TEXT,PRIMARY KEY(month,id))')
        c.execute('CREATE TABLE holiday_frozen_review(month TEXT,id INTEGER,detail TEXT NOT NULL,PRIMARY KEY(month,id))')
        c.execute('INSERT INTO holiday_freeze SELECT month FROM months WHERE closed=1')
        c.execute('CREATE TRIGGER holiday_identity_insert AFTER INSERT ON records BEGIN INSERT INTO holiday_identity_records '+projection+' WHERE r.id=NEW.id; END')
        c.execute('CREATE TRIGGER holiday_identity_delete AFTER DELETE ON records BEGIN DELETE FROM holiday_identity_records WHERE id=OLD.id; END')
        for table in ('holidays','municipality_bindings'):
            for event in ('INSERT','UPDATE','DELETE'):
                c.execute(f'CREATE TRIGGER holiday_revision_{table}_{event} AFTER {event} ON {table} BEGIN UPDATE cache_revision SET revision=revision+1 WHERE id=1; END')
        c.execute('PRAGMA user_version=4');c.commit()
    except Exception:c.rollback();raise

def connection():
    import storage
    return closing(storage.connect())

def calendar():
    with connection() as c:return [dict(r) for r in c.execute('SELECT * FROM holidays ORDER BY day,scope,state,municipality')]

def save(day,description,scope,state='',municipality='',holiday_id=None):
    day=date.fromisoformat(str(day)).isoformat();state=state.strip().upper();town=core.norm(municipality)
    if not description.strip() or scope not in ('Nacional','Estadual','Municipal'):raise ValueError('Informe descrição e abrangência válida.')
    if scope=='Nacional':state=town=''
    elif state not in UFS:raise ValueError('Informe uma UF válida.')
    if scope=='Estadual':town=''
    if scope=='Municipal' and not town:raise ValueError('Informe o município.')
    import storage
    with connection() as c:
        c.execute('BEGIN IMMEDIATE')
        try:
            if holiday_id is None:c.execute('INSERT INTO holidays(day,description,scope,state,municipality) VALUES(?,?,?,?,?)',(day,description.strip(),scope,state,town))
            elif c.execute('UPDATE holidays SET day=?,description=?,scope=?,state=?,municipality=? WHERE id=?',(day,description.strip(),scope,state,town,holiday_id)).rowcount!=1:raise ValueError('Feriado não encontrado.')
        except sqlite3.IntegrityError:raise ValueError('Já existe feriado com essa data e abrangência.') from None
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES(?,?,?,?)',(day[:7],'Calendário de feriados',json.dumps({'data':day,'descricao':description,'abrangencia':scope,'uf':state,'municipio':town},ensure_ascii=False),storage.now()))
        c.commit()

def delete(holiday_id):
    import storage
    with connection() as c:
        c.execute('BEGIN IMMEDIATE');row=c.execute('SELECT * FROM holidays WHERE id=?',(holiday_id,)).fetchone()
        if not row:raise ValueError('Feriado não encontrado.')
        c.execute('DELETE FROM holidays WHERE id=?',(holiday_id,))
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES(?,?,?,?)',(row['day'][:7],'Excluir feriado',json.dumps(dict(row)),storage.now()))
        c.commit()

def bind(source,municipality,state):
    source=core.norm(source);town=core.norm(municipality);state=state.strip().upper()
    if not source or not town or state not in UFS:raise ValueError('Informe origem, município e UF válidos.')
    import storage
    with connection() as c:
        c.execute('BEGIN IMMEDIATE');c.execute('INSERT INTO municipality_bindings VALUES(?,?,?) ON CONFLICT(source) DO UPDATE SET municipality=excluded.municipality,state=excluded.state',(source,town,state))
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES(?,?,?,?)',(None,'Confirmar município',json.dumps({'origem':source,'municipio':town,'uf':state}),storage.now()))
        c.commit()

def candidate_sql(month,start=None,end=None,omit_id=None,restore_id=None):
    args=[month];period=''
    if start is not None:period=' AND m.day BETWEEN ? AND ?';args.extend([start,end])
    sql="""WITH resolved AS (
        SELECT m.*,p.supply,p.execution,p.eligible,
          COALESCE(NULLIF(b.municipality,''),NULLIF(a.municipality,''),'') municipality,
          COALESCE(NULLIF(b.state,''),NULLIF(a.state,''),'') state,
          CASE WHEN b.source IS NOT NULL OR proof.import_id IS NOT NULL THEN 'BR' ELSE COALESCE(a.country,'') END country,
          CASE WHEN b.source IS NOT NULL THEN 'Identificação manual confirmada'
               WHEN proof.import_id IS NOT NULL THEN 'Execução no Brasil comprovada: '||proof.evidence ELSE a.evidence END location_evidence
        FROM record_metrics m JOIN holiday_identity_records p ON p.id=m.id
        LEFT JOIN municipality_bindings b ON b.source=p.source
        LEFT JOIN automatic_localities a ON a.source=p.source
        LEFT JOIN import_brazil_proofs proof ON proof.import_id=m.import_id
    ) SELECT m.id,m.day,m.employee,m.city,m.group_name,m.supply,m.execution,m.municipality,m.state,m.country,m.location_evidence,
      CASE WHEN strftime('%w',m.day)='0' THEN 'Domingo: conferir'
           WHEN m.supply='' OR m.execution='' THEN 'Fornecimento/execução ausente'
           WHEN EXISTS(SELECT 1 FROM holidays h WHERE h.day=m.day AND
             ((h.scope='Nacional' AND m.country='BR') OR (h.scope='Estadual' AND m.state<>'' AND h.state=m.state)
              OR (h.scope='Municipal' AND m.state<>'' AND m.municipality<>'' AND h.state=m.state AND h.municipality=m.municipality))) THEN 'Elegível'
           WHEN EXISTS(SELECT 1 FROM holidays h WHERE h.day=m.day AND h.scope='Nacional') AND m.country<>'BR' THEN 'Execução no Brasil não comprovada'
           WHEN EXISTS(SELECT 1 FROM holidays h WHERE h.day=m.day AND h.scope='Estadual') AND m.state='' THEN 'UF não confirmada'
           WHEN EXISTS(SELECT 1 FROM holidays h WHERE h.day=m.day AND h.scope='Municipal') AND (m.state='' OR m.municipality='') THEN 'Município/UF não confirmado'
           ELSE 'Não aplicável' END status
      FROM resolved m WHERE m.month=? AND m.excluded=0 AND m.import_deleted=0 AND m.day IS NOT NULL
        AND ((m.eligible=1 AND EXISTS(SELECT 1 FROM holidays h WHERE h.day=m.day)) OR strftime('%w',m.day)='0')"""+period
    if omit_id is not None:sql+=' AND m.import_id<>?';args.append(omit_id)
    if restore_id is not None:
        sql=sql.replace('m.import_deleted=0','(m.import_deleted=0 OR m.import_id=?)')
        args.insert(1,restore_id)
    return sql,args

def charges_query(c,month,start=None,end=None,omit_id=None,restore_id=None):
    period=' AND m.day BETWEEN ? AND ?' if start is not None else ''
    if c.execute('SELECT 1 FROM holiday_freeze WHERE month=?',(month,)).fetchone():
        return ('SELECT m.*,f.municipality,f.state FROM holiday_frozen_records f JOIN record_metrics m ON m.id=f.id WHERE f.month=?'+period,[month,*([start,end] if start is not None else [])])
    sql,args=candidate_sql(month,start,end,omit_id,restore_id)
    return ('''WITH candidates AS ('''+sql+''') SELECT * FROM candidates WHERE status='Elegível'
        AND id IN (SELECT MIN(id) FROM candidates WHERE status='Elegível' GROUP BY supply,day,execution
          HAVING COUNT(DISTINCT municipality||'/'||state)=1) ORDER BY id''',args)

def charges(c,month,start=None,end=None):
    sql,args=charges_query(c,month,start,end)
    return c.execute(sql,args).fetchall()

def overview(month,start=None,end=None):
    with connection() as c:
        charge_sql,charge_args=charges_query(c,month,start,end)
        quantity=c.execute('SELECT COUNT(*) FROM ('+charge_sql+')',charge_args).fetchone()[0]
        frozen=c.execute('SELECT 1 FROM holiday_freeze WHERE month=?',(month,)).fetchone()
        sql,args=candidate_sql(month,start,end)
        frozen_period=" AND json_extract(detail,'$.day') BETWEEN ? AND ?" if start is not None else ''
        stats=c.execute('SELECT status,COUNT(*) n FROM ('+sql+') GROUP BY status',args).fetchall() if not frozen else c.execute("SELECT json_extract(detail,'$.status') status,COUNT(*) n FROM holiday_frozen_review WHERE month=?"+frozen_period+' GROUP BY status',[month,*([start,end] if start is not None else [])]).fetchall()
        divergent=c.execute("SELECT COALESCE(SUM(n),0) FROM (SELECT COUNT(*) n FROM ("+sql+") WHERE status='Elegível' GROUP BY supply,day,execution HAVING COUNT(DISTINCT municipality||'/'||state)>1)",args).fetchone()[0] if not frozen else 0
    pending=divergent+sum(r['n'] for r in stats if r['status'] in ('Município/UF não confirmado','UF não confirmada','Execução no Brasil não comprovada','Fornecimento/execução ausente','Domingo: conferir'))
    return {'holiday_quantity':quantity,'holiday_pending':pending}

def productivity(month,by,start=None,end=None):
    column={'employee':'employee','city':'city','group':'group_name'}[by];out={}
    with connection() as c:
        sql,args=charges_query(c,month,start,end)
        for row in c.execute('SELECT '+column+' name,COUNT(*) n FROM ('+sql+') GROUP BY '+column,args):out[row['name']]=row['n']
    return out

def page(month,start=None,end=None,offset=0,limit=100,municipality=None,group=None,employee=None):
    if limit>500 or limit<1 or offset<0:raise ValueError('Página inválida.')
    with connection() as c:
        sql,args=candidate_sql(month,start,end)
        if c.execute('SELECT 1 FROM holiday_freeze WHERE month=?',(month,)).fetchone():
            condition='month=?';params=[month]
            if start is not None:condition+=" AND json_extract(detail,'$.day') BETWEEN ? AND ?";params.extend([start,end])
            for key,value in [('municipality',municipality),('group_name',group),('employee',employee)]:
                if value is not None:
                    expression="COALESCE(json_extract(detail,'$.municipality'),'')||'/'||COALESCE(json_extract(detail,'$.state'),'')" if key=='municipality' else "json_extract(detail,'$."+key+"')"
                    condition+=' AND '+expression+'=?';params.append(value)
            count=c.execute('SELECT COUNT(*) FROM holiday_frozen_review WHERE '+condition,params).fetchone()[0]
            rows=c.execute('SELECT detail FROM holiday_frozen_review WHERE '+condition+' ORDER BY id LIMIT ? OFFSET ?',[*params,limit,offset]).fetchall()
            return count,[json.loads(r['detail']) for r in rows]
        condition="status<>'Não aplicável'";extra=[]
        for key,value in [('municipality',municipality),('group_name',group),('employee',employee)]:
            if value is not None:
                condition+=" AND "+("COALESCE(municipality,'')||'/'||COALESCE(state,'')" if key=='municipality' else key)+'=?';extra.append(value)
        count=c.execute('SELECT COUNT(*) FROM ('+sql+') WHERE '+condition,[*args,*extra]).fetchone()[0]
        rows=c.execute('SELECT * FROM ('+sql+') WHERE '+condition+' ORDER BY day,id LIMIT ? OFFSET ?',[*args,*extra,limit,offset]).fetchall()
        charge_sql,charge_args=charges_query(c,month,start,end)
        page_ids=[r['id'] for r in rows]
        ids={r[0] for r in c.execute('SELECT id FROM ('+charge_sql+') WHERE id IN ('+','.join('?' for _ in page_ids)+')',[*charge_args,*page_ids])} if page_ids else set()
    return count,[{**dict(r),'status':('Execução duplicada ou divergente: conferir' if r['status']=='Elegível' and r['id'] not in ids else r['status']),
                  'Cobrado':r['id'] in ids,'Valor (R$)':1.05 if r['id'] in ids else 0} for r in rows]

def freeze(c,month,closed):
    if closed:
        if c.execute('SELECT 1 FROM holiday_freeze WHERE month=?',(month,)).fetchone():return
        rows=charges(c,month)
        c.executemany('INSERT INTO holiday_frozen_records VALUES(?,?,?,?)',[(month,r['id'],r['municipality'],r['state']) for r in rows])
        ids={r['id'] for r in rows};sql,args=candidate_sql(month)
        c.executemany('INSERT INTO holiday_frozen_review VALUES(?,?,?)',
                     [(month,r['id'],json.dumps({**dict(r),'Cobrado':r['id'] in ids,'Valor (R$)':1.05 if r['id'] in ids else 0},ensure_ascii=False))
                      for r in c.execute(sql,args) if r['status']!='Não aplicável'])
        c.execute('INSERT INTO holiday_freeze VALUES(?)',(month,))
    else:
        c.execute('DELETE FROM holiday_frozen_records WHERE month=?',(month,));c.execute('DELETE FROM holiday_freeze WHERE month=?',(month,))
        c.execute('DELETE FROM holiday_frozen_review WHERE month=?',(month,))

def import_impact(c,month,import_id,deleted):
    sql,args=charges_query(c,month)
    before=c.execute('SELECT COUNT(*) FROM ('+sql+')',args).fetchone()[0]
    owned=c.execute('SELECT COUNT(*) FROM ('+sql+') WHERE id IN (SELECT id FROM records WHERE import_id=?)',[*args,import_id]).fetchone()[0]
    sql,args=charges_query(c,month,omit_id=None if deleted else import_id,restore_id=import_id if deleted else None)
    after=c.execute('SELECT COUNT(*) FROM ('+sql+')',args).fetchone()[0]
    return owned*UNIT,(after-before if deleted else before-after)*UNIT

def filter_options(month,start=None,end=None):
    with connection() as c:
        sql,args=candidate_sql(month,start,end)
        if c.execute('SELECT 1 FROM holiday_freeze WHERE month=?',(month,)).fetchone():
            sql="SELECT json_extract(detail,'$.municipality') municipality,json_extract(detail,'$.state') state,json_extract(detail,'$.group_name') group_name,json_extract(detail,'$.employee') employee,json_extract(detail,'$.status') status FROM holiday_frozen_review WHERE month=?"
            args=[month]
            if start is not None:sql+=" AND json_extract(detail,'$.day') BETWEEN ? AND ?";args.extend([start,end])
        return {key:[r[0] for r in c.execute('SELECT DISTINCT '+expression+' FROM ('+sql+") WHERE status<>'Não aplicável' ORDER BY 1",args)]
                for key,expression in [('municipality',"COALESCE(municipality,'')||'/'||COALESCE(state,'')"),('group','group_name'),('employee','employee')]}
