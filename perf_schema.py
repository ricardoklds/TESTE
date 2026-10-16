"""Projeção de leitura dos resultados existentes; nunca refaz regras financeiras."""
import json
from uuid import uuid4
import sqlite3
import periods


def reading_day(raw, mapping):
    column=json.loads(mapping).get('date')
    value=periods.parse_date(json.loads(raw).get(column)) if column else None
    return value.isoformat() if value else None


def prepare(c, data):
    c.create_function('reading_day',2,reading_day,deterministic=True)
    if c.execute('PRAGMA user_version').fetchone()[0]>=3:return
    folder=data/'backups';folder.mkdir(exist_ok=True)
    with sqlite3.connect(folder/('antes-migracao-v3-'+uuid4().hex+'.sqlite3')) as backup:
        c.backup(backup)
        if backup.execute('PRAGMA integrity_check').fetchone()[0]!='ok':
            raise ValueError('Backup inválido; migração de desempenho cancelada.')
    try:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('PRAGMA user_version').fetchone()[0]>=3:c.commit();return
        c.execute('''CREATE TABLE record_metrics (
            id INTEGER PRIMARY KEY,month TEXT NOT NULL,import_id INTEGER NOT NULL,day TEXT,
            employee TEXT,city TEXT,group_name TEXT,business_key TEXT,errors INTEGER,alerts INTEGER,
            u138 INTEGER,u128 INTEGER,u137 INTEGER,uprint INTEGER,uop INTEGER,
            excluded INTEGER,import_deleted INTEGER)''')
        projection='''SELECT r.id,r.month,r.import_id,reading_day(r.raw,i.mapping),
            json_extract(r.result,'$.employee'),json_extract(r.result,'$.city'),json_extract(r.result,'$.group'),
            json_extract(r.result,'$.key'),json_array_length(json_extract(r.result,'$.errors')),
            json_array_length(json_extract(r.result,'$.alerts')),
            json_extract(r.result,'$.units."138"'),json_extract(r.result,'$.units."128"'),
            json_extract(r.result,'$.units."137"'),json_extract(r.result,'$.units.impressao'),
            json_extract(r.result,'$.units.apontamento'),r.excluded,r.import_deleted
            FROM records r JOIN imports i ON i.id=r.import_id'''
        c.execute('INSERT INTO record_metrics '+projection)
        if c.execute('SELECT COUNT(*) FROM record_metrics').fetchone()[0]!=c.execute('SELECT COUNT(*) FROM records').fetchone()[0]:
            raise ValueError('Há registros sem importação correspondente. Migração cancelada; backup preservado.')
        c.execute('CREATE INDEX metrics_month_day ON record_metrics(month,day,id)')
        c.execute('CREATE INDEX metrics_import ON record_metrics(import_id,id)')
        c.execute('CREATE INDEX metrics_business ON record_metrics(month,business_key,id) WHERE excluded=0 AND import_deleted=0')
        c.execute('CREATE INDEX records_import ON records(import_id,month,id)')
        c.execute('CREATE INDEX records_month_id ON records(month,id)')
        c.execute('CREATE INDEX audit_month ON audit(month,id)')
        c.execute('CREATE TABLE cache_revision(id INTEGER PRIMARY KEY CHECK(id=1),revision INTEGER NOT NULL)')
        c.execute('INSERT INTO cache_revision VALUES(1,1)')
        c.execute('CREATE TRIGGER metrics_insert AFTER INSERT ON records BEGIN INSERT INTO record_metrics '+projection.replace('FROM records r JOIN imports i ON i.id=r.import_id','FROM records r JOIN imports i ON i.id=r.import_id WHERE r.id=NEW.id')+'; END')
        c.execute('''CREATE TRIGGER metrics_update AFTER UPDATE OF excluded,import_deleted ON records
            BEGIN UPDATE record_metrics SET excluded=NEW.excluded,import_deleted=NEW.import_deleted WHERE id=NEW.id; END''')
        c.execute('CREATE TRIGGER metrics_delete AFTER DELETE ON records BEGIN DELETE FROM record_metrics WHERE id=OLD.id; END')
        # One revision per committed audit event, not one cache write per imported row.
        for table in ('audit','settings'):
            for event in ('INSERT','UPDATE','DELETE'):
                c.execute(f'CREATE TRIGGER revision_{table}_{event} AFTER {event} ON {table} BEGIN UPDATE cache_revision SET revision=revision+1 WHERE id=1; END')
        c.execute('PRAGMA user_version=3');c.commit()
    except Exception:
        c.rollback();raise
