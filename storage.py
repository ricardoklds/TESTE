import hashlib
import json
import os
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from core import CATEGORIES, evaluate, fingerprint

DATA = Path(os.environ.get('APP_DATA_DIR', str(Path(__file__).parent / 'data')))

def connect():
    DATA.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DATA / 'contrato.sqlite3')
    c.row_factory = sqlite3.Row
    c.executescript('''
    CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS months (month TEXT PRIMARY KEY, prices TEXT NOT NULL, closed INTEGER NOT NULL DEFAULT 0, closed_at TEXT);
    CREATE TABLE IF NOT EXISTS imports (id INTEGER PRIMARY KEY, month TEXT NOT NULL, name TEXT NOT NULL, sha TEXT NOT NULL, sheet TEXT NOT NULL, mapping TEXT NOT NULL, headers TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(month,sha,sheet));
    CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, month TEXT NOT NULL, import_id INTEGER NOT NULL, line INTEGER NOT NULL, fingerprint TEXT NOT NULL, raw TEXT NOT NULL, result TEXT NOT NULL, excluded INTEGER NOT NULL DEFAULT 0, reason TEXT, UNIQUE(month,fingerprint));
    CREATE TABLE IF NOT EXISTS audit (id INTEGER PRIMARY KEY, month TEXT, action TEXT, detail TEXT, created_at TEXT);
    ''')
    return c

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

def import_sheet(content, name, parsed, mapping, month):
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
        info = month_info(month)
        if info['closed']:
            raise ValueError('Mês fechado. Reabra antes de importar.')
        c.execute('INSERT OR IGNORE INTO months(month,prices) VALUES (?,?)', (month, json.dumps(info['prices'])))
        try:
            cur = c.execute('INSERT INTO imports(month,name,sha,sheet,mapping,headers,created_at) VALUES (?,?,?,?,?,?,?)',
                (month, Path(name).name, sha, parsed['sheet'], json.dumps(mapping), json.dumps(parsed['headers']), now()))
        except sqlite3.IntegrityError:
            raise ValueError('Esta aba deste arquivo já foi importada neste mês.') from None
        for row in parsed['records']:
            raw = row['raw']; result = evaluate(raw, mapping, month)
            cur2 = c.execute('INSERT OR IGNORE INTO records(month,import_id,line,fingerprint,raw,result) VALUES (?,?,?,?,?,?)',
                (month, cur.lastrowid, row['line'], fingerprint(raw), json.dumps(raw, ensure_ascii=False), json.dumps(result, ensure_ascii=False)))
            added += cur2.rowcount
            skipped += 1 - cur2.rowcount
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES (?,?,?,?)',
            (month,'Importação',json.dumps({'arquivo':Path(name).name,'sha256':sha,'inseridos':added,'duplicados_ignorados':skipped}),now()))
    return added, skipped

def records(month):
    with connect() as c:
        rows = c.execute('SELECT r.*,i.name,i.sheet FROM records r JOIN imports i ON i.id=r.import_id WHERE r.month=? ORDER BY r.id', (month,)).fetchall()
    return [{**dict(r), 'raw':json.loads(r['raw']), 'result':json.loads(r['result'])} for r in rows]

def conflicts(rows):
    groups = {}
    for r in rows:
        key = r['result']['key']
        if key and not r['excluded']:
            groups.setdefault(key, []).append(r['id'])
    return [ids for ids in groups.values() if len(ids)>1]

def exclude(month, row_id, reason, excluded=True):
    if not reason.strip():
        raise ValueError('Informe o motivo para registrar a decisão.')
    with connect() as c:
        if month_info(month)['closed']:
            raise ValueError('Reabra o mês primeiro.')
        if c.execute('UPDATE records SET excluded=?,reason=? WHERE id=? AND month=?', (int(excluded),reason,row_id,month)).rowcount != 1:
            raise ValueError('Registro não encontrado.')
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES (?,?,?,?)', (month,'Exclusão' if excluded else 'Reinclusão',f'ID {row_id}: {reason}',now()))

def close_month(month, closed=True, reason=''):
    rows = records(month)
    if closed and (not rows or conflicts(rows) or any(r['result']['errors'] for r in rows if not r['excluded'])):
        raise ValueError('Resolva os erros e chaves repetidas antes de fechar; o mês precisa ter registros.')
    if not closed and not reason.strip():
        raise ValueError('Informe o motivo da reabertura.')
    with connect() as c:
        c.execute('UPDATE months SET closed=?,closed_at=? WHERE month=?', (int(closed),now() if closed else None,month))
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES (?,?,?,?)', (month,'Fechamento' if closed else 'Reabertura',reason,now()))

def update_month_prices(month, prices):
    with connect() as c:
        if month_info(month)['closed']:
            raise ValueError('Mês fechado: preços preservados.')
        c.execute('UPDATE months SET prices=? WHERE month=?', (json.dumps(prices),month))
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES (?,?,?,?)',(month,'Atualização de preços',json.dumps(prices),now()))

def imports(month):
    with connect() as c:
        return [dict(r) for r in c.execute('SELECT * FROM imports WHERE month=?',(month,))]

def audit(month):
    with connect() as c:
        return [dict(r) for r in c.execute('SELECT action,detail,created_at FROM audit WHERE month=? ORDER BY id DESC',(month,))]
