from audit_text import audit_text
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4
from core import CATEGORIES, evaluate, fingerprint

DATA = Path(os.environ.get('APP_DATA_DIR', str(Path(__file__).parent / 'data')))

def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DATA / 'contrato.sqlite3')
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA busy_timeout=30000')
    existing = c.execute("SELECT 1 FROM sqlite_master WHERE name='records'").fetchone()
    if existing and c.execute('PRAGMA user_version').fetchone()[0] < 2:
        # Take a consistent, verified SQLite backup BEFORE any schema change.
        backup_dir = DATA / 'backups'; backup_dir.mkdir(exist_ok=True)
        target = backup_dir / ('antes-migracao-v2-' + uuid4().hex + '.sqlite3')
        with sqlite3.connect(target) as backup:
            c.backup(backup)
            if backup.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                c.close(); raise ValueError('Backup inválido; migração cancelada.')
        try:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('PRAGMA user_version').fetchone()[0] < 2:
                c.execute('ALTER TABLE imports ADD COLUMN deleted INTEGER NOT NULL DEFAULT 0')
                c.execute('''CREATE TABLE records_v2 (id INTEGER PRIMARY KEY, month TEXT NOT NULL,
                    import_id INTEGER NOT NULL, line INTEGER NOT NULL, fingerprint TEXT NOT NULL,
                    raw TEXT NOT NULL, result TEXT NOT NULL, excluded INTEGER NOT NULL DEFAULT 0,
                    reason TEXT, import_deleted INTEGER NOT NULL DEFAULT 0)''')
                c.execute('INSERT INTO records_v2(id,month,import_id,line,fingerprint,raw,result,excluded,reason) SELECT id,month,import_id,line,fingerprint,raw,result,excluded,reason FROM records')
                c.execute('DROP TABLE records')
                c.execute('ALTER TABLE records_v2 RENAME TO records')
                c.execute('CREATE UNIQUE INDEX active_fingerprints ON records(month,fingerprint) WHERE import_deleted=0')
                c.execute('PRAGMA user_version=2')
            c.commit()
        except Exception:
            c.rollback();c.close();raise
    if existing:
        from perf_schema import prepare
        prepare(c,DATA)
        from holidays import prepare as prepare_holidays
        prepare_holidays(c,DATA)
        from localities import prepare as prepare_localities
        prepare_localities(c,DATA)
        return c
    c.executescript('''
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS months (month TEXT PRIMARY KEY, prices TEXT NOT NULL, closed INTEGER NOT NULL DEFAULT 0, closed_at TEXT);
    CREATE TABLE IF NOT EXISTS imports (id INTEGER PRIMARY KEY, month TEXT NOT NULL, name TEXT NOT NULL, sha TEXT NOT NULL, sheet TEXT NOT NULL, mapping TEXT NOT NULL, headers TEXT NOT NULL, created_at TEXT NOT NULL, deleted INTEGER NOT NULL DEFAULT 0, UNIQUE(month,sha,sheet));
    CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, month TEXT NOT NULL, import_id INTEGER NOT NULL, line INTEGER NOT NULL, fingerprint TEXT NOT NULL, raw TEXT NOT NULL, result TEXT NOT NULL, excluded INTEGER NOT NULL DEFAULT 0, reason TEXT, import_deleted INTEGER NOT NULL DEFAULT 0);
    CREATE UNIQUE INDEX IF NOT EXISTS active_fingerprints ON records(month,fingerprint) WHERE import_deleted=0;
    CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, month TEXT, action TEXT, detail TEXT, created_at TEXT);
    ''')
    c.execute('PRAGMA user_version=2')
    from perf_schema import prepare
    prepare(c,DATA)
    from holidays import prepare as prepare_holidays
    prepare_holidays(c,DATA)
    from localities import prepare as prepare_localities
    prepare_localities(c,DATA)
    return c

def ensure_open(c, month):
    r = c.execute('SELECT closed FROM months WHERE month=?',(month,)).fetchone()
    if r and r['closed']:
        raise ValueError('Mês fechado. Reabra antes de alterar importações ou registros.')

def now():
    return datetime.now(timezone.utc).isoformat()

def settings():
    with connect() as c:
        return {r['key']: json.loads(r['value']) for r in c.execute('SELECT * FROM settings')}

def save_setting(key, value):
    with connect() as c:
        c.execute('INSERT OR REPLACE INTO settings VALUES (?,?)', (key, json.dumps(value)))

def month_info(month):
    with connect() as c:
        r = c.execute('SELECT * FROM months WHERE month=?', (month,)).fetchone()
    if r:
        return {**dict(r), 'prices': json.loads(r['prices'])}
    return {'month': month, 'closed': 0, 'prices': settings().get('prices', {k: v[2] for k,v in CATEGORIES.items()})}

def import_sheet(content, name, parsed, mapping, month, on_progress=None):
    if any(not mapping.get(k) for k in ('printed','retained','cause','copies','operational')):
        raise ValueError('Mapeie as cinco colunas obrigatórias.')
    if len([v for v in mapping.values() if v]) != len(set(v for v in mapping.values() if v)):
        raise ValueError('Uma coluna não pode representar dois campos.')
    sha = hashlib.sha256(content).hexdigest()
    original = DATA / 'originais' / (sha + '.xlsx')
    original.parent.mkdir(parents=True, exist_ok=True)
    if original.exists():
        if hashlib.sha256(original.read_bytes()).hexdigest() != sha:
            raise ValueError('A cópia arquivada falhou na conferência de integridade.')
    else:
        original.write_bytes(content)
    if hashlib.sha256(original.read_bytes()).hexdigest() != sha:
        raise ValueError('Falha na preservação do original.')
    added = skipped = 0
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        ensure_open(c,month)
        info = month_info(month)
        if info['closed']:
            raise ValueError('Mês fechado. Reabra antes de importar.')
        c.execute('INSERT OR IGNORE INTO months(month,prices) VALUES (?,?)', (month, json.dumps(info['prices'])))
        try:
            cur = c.execute('INSERT INTO imports(month,name,sha,sheet,mapping,headers,created_at) VALUES (?,?,?,?,?,?,?)',
                (month, Path(name).name, sha, parsed['sheet'], json.dumps(mapping), json.dumps(parsed['headers']), now()))
        except sqlite3.IntegrityError:
            raise ValueError('Esta aba já existe neste mês. Se excluída, use Restaurar importação. Para uma correção, importe o arquivo corrigido.') from None
        batch=[]
        def insert_batch(batch):
            result=c.executemany('INSERT OR IGNORE INTO records(month,import_id,line,fingerprint,raw,result) VALUES (?,?,?,?,?,?)',batch)
            return result.rowcount
        for row in parsed['records']:
            raw = row['raw']; result = evaluate(raw, mapping, month)
            batch.append((month,cur.lastrowid,row['line'],fingerprint(raw),json.dumps(raw,ensure_ascii=False),json.dumps(result,ensure_ascii=False)))
            if len(batch)>=1000:
                count=insert_batch(batch);added+=count;skipped+=len(batch)-count;batch=[]
                if on_progress:on_progress(added+skipped,added,skipped)
        if batch:
            count=insert_batch(batch);added+=count;skipped+=len(batch)-count
            if on_progress:on_progress(added+skipped,added,skipped)
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES (?,?,?,?)',
            (month,'Importação',json.dumps({'arquivo':Path(name).name,'sha256':sha,'inseridos':added,'duplicados_ignorados':skipped}),now()))
    return added, skipped

def records(month, connection=None):
    c=connection or connect()
    try:
        rows = c.execute('SELECT r.*,i.name,i.sheet FROM records r JOIN imports i ON i.id=r.import_id WHERE r.month=? ORDER BY r.id', (month,)).fetchall()
    finally:
        if connection is None:c.close()
    return [{**dict(r), 'record_excluded':r['excluded'], 'excluded':int(bool(r['excluded'] or r['import_deleted'])),
             'raw':json.loads(r['raw']), 'result':json.loads(r['result'])} for r in rows]

def conflicts(rows):
    groups = {}
    for r in rows:
        key = r['result']['key']
        if key and not r['excluded']:
            groups.setdefault(key, []).append(r['id'])
    return [ids for ids in groups.values() if len(ids)>1]

def exclude(month, row_id, reason=None, excluded=True):
    reason=audit_text(reason)
    with connect() as c:
        c.execute('BEGIN IMMEDIATE');ensure_open(c,month)
        row=c.execute('SELECT import_deleted FROM records WHERE id=? AND month=?',(row_id,month)).fetchone()
        if row and row['import_deleted']:
            raise ValueError('Importação excluída: restaure o arquivo na tela Importar planilhas.')
        if c.execute('UPDATE records SET excluded=?,reason=? WHERE id=? AND month=?', (int(excluded),reason,row_id,month)).rowcount != 1:
            raise ValueError('Registro não encontrado.')
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES (?,?,?,?)', (month,'Exclusão' if excluded else 'Reinclusão',f'ID {row_id}: {reason}',now()))

def close_month(month, closed=True, reason=''):
    reason=audit_text(reason)
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        status=c.execute('SELECT COUNT(*) active,COALESCE(SUM(errors>0),0) errors FROM record_metrics WHERE month=? AND excluded=0 AND import_deleted=0',(month,)).fetchone()
        duplicate=c.execute('SELECT 1 FROM record_metrics WHERE month=? AND excluded=0 AND import_deleted=0 AND business_key IS NOT NULL GROUP BY business_key HAVING COUNT(*)>1 LIMIT 1',(month,)).fetchone()
        if closed and (not status['active'] or status['errors'] or duplicate):
            raise ValueError('Resolva os erros e chaves repetidas antes de fechar; o mês precisa ter registros ativos.')
        from holidays import freeze
        freeze(c,month,closed)
        c.execute('UPDATE months SET closed=?,closed_at=? WHERE month=?', (int(closed),now() if closed else None,month))
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES (?,?,?,?)', (month,'Fechamento' if closed else 'Reabertura',reason,now()))

def update_month_prices(month, prices):
    with connect() as c:
        c.execute('BEGIN IMMEDIATE');ensure_open(c,month)
        c.execute('UPDATE months SET prices=? WHERE month=?', (json.dumps(prices),month))
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES (?,?,?,?)',(month,'Atualização de preços',json.dumps(prices),now()))

def imports(month):
    with connect() as c:
        return [dict(r) for r in c.execute('SELECT * FROM imports WHERE month=? ORDER BY id',(month,))]

def import_preview(month, import_id, connection=None):
    c=connection or connect()
    try:
        entry=c.execute('SELECT * FROM imports WHERE id=? AND month=?',(import_id,month)).fetchone()
        if not entry:raise ValueError('Importação não encontrada neste mês.')
        month_row=c.execute('SELECT prices,closed FROM months WHERE month=?',(month,)).fetchone()
        prices=json.loads(month_row['prices'])
        stats=c.execute('''SELECT COUNT(*) records,COALESCE(SUM(excluded=0),0) billable,
            COALESCE(SUM(CASE WHEN excluded=0 THEN u138 ELSE 0 END),0) "138",
            COALESCE(SUM(CASE WHEN excluded=0 THEN u128 ELSE 0 END),0) "128",
            COALESCE(SUM(CASE WHEN excluded=0 THEN u137 ELSE 0 END),0) "137",
            COALESCE(SUM(CASE WHEN excluded=0 THEN uprint ELSE 0 END),0) impressao,
            COALESCE(SUM(CASE WHEN excluded=0 THEN uop ELSE 0 END),0) apontamento
            FROM record_metrics WHERE import_id=? AND month=?''',(import_id,month)).fetchone()
        potential=sum(stats[k]*prices[k] for k in CATEGORIES)
        from holidays import import_impact
        owned_holiday,holiday_delta=import_impact(c,month,import_id,bool(entry['deleted']))
        # Detect any change between confirmation and commit, including prices or row decisions.
        version=fingerprint({'entry':dict(entry),'month':dict(month_row),'revision':c.execute('SELECT revision FROM cache_revision WHERE id=1').fetchone()[0]})
        return {**dict(entry),'record_count':stats['records'],'active_count':0 if entry['deleted'] else stats['billable'],
                'potential_count':stats['billable'],'total_cents':0 if entry['deleted'] else potential+owned_holiday,
                'potential_cents':potential+holiday_delta,'version':version}
    finally:
        if connection is None:c.close()

def set_import_deleted(month, import_id, deleted, reason=None, expected_version=None):
    reason=audit_text(reason)
    with connect() as c:
        c.execute('BEGIN IMMEDIATE');ensure_open(c,month)
        preview=import_preview(month,import_id,c)
        if expected_version is not None and expected_version != preview['version']:
            raise ValueError('Dados ou preços mudaram. Abra a confirmação novamente para conferir o impacto atualizado.')
        if bool(preview['deleted'])==bool(deleted):raise ValueError('A importação já está nessa situação.')
        if not deleted:
            repeated=c.execute('''SELECT COUNT(*) FROM records old JOIN records current
                ON current.month=old.month AND current.fingerprint=old.fingerprint
                AND current.import_deleted=0 AND current.import_id<>old.import_id
                WHERE old.month=? AND old.import_id=?''',(month,import_id)).fetchone()[0]
            if repeated:raise ValueError(f'Restauração bloqueada: {repeated} registros já pertencem a importações ativas. Exclua a importação substituta antes de restaurar; nenhum registro foi alterado.')
        c.execute('UPDATE imports SET deleted=? WHERE id=? AND month=?',(int(deleted),import_id,month))
        c.execute('UPDATE records SET import_deleted=? WHERE import_id=? AND month=?',(int(deleted),import_id,month))
        detail={'import_id':import_id,'arquivo':preview['name'],'aba':preview['sheet'],'mes':month,
                'registros_vinculados':preview['record_count'],'registros_removidos_ou_restaurados':preview['potential_count'],
                'impacto_centavos':preview['potential_cents'],'justificativa':reason.strip()}
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES (?,?,?,?)',
                  (month,'Excluir importação' if deleted else 'Restaurar importação',json.dumps(detail,ensure_ascii=False),now()))
    return detail

def audit(month):
    with connect() as c:
        return [dict(r) for r in c.execute('SELECT action,detail,created_at FROM audit WHERE month=? ORDER BY id DESC',(month,))]
