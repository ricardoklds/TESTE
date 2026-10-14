"""Resolução exata com cadastro versionado de códigos IBGE; sem fuzzy matching."""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
import sqlite3
from uuid import uuid4
import core

EXPECTED_SHA='72e96f8c4044bdba30397231a7695a36c9f4134b984f954d5fd65b22675f1702'

@lru_cache(maxsize=1)
def municipal_confirmations():
    """Confirmações documentais externas ao banco, apenas para contexto municipal.

    Não substitui resolve(), nem as decisões nacionais/estaduais já existentes.
    """
    path=Path(__file__).parent/'reference_data'/'municipal_confirmations.json'
    entries=json.loads(path.read_text(encoding='utf-8'));_,codes,_=reference()
    result=[];seen=set()
    for entry in entries:
        source=core.norm(entry['source']);r=codes.get(entry['ibge_id'])
        if not r or r['state']!=entry['state'] or entry['scope']!='Municipal' or source in seen or not entry['evidence'].strip():
            raise ValueError('Confirmação municipal inválida; atualização cancelada.')
        seen.add(source);result.append((source,core.norm(r['name']),r['state'],entry['evidence']))
    return tuple(result)

@lru_cache(maxsize=1)
def reference():
    content=(Path(__file__).parent/'reference_data'/'municipalities.json').read_bytes()
    if hashlib.sha256(content).hexdigest()!=EXPECTED_SHA:raise ValueError('Referência municipal ausente ou alterada; identificação automática cancelada.')
    rows=json.loads(content);names={};codes={}
    for r in rows:names.setdefault(core.norm(r['name']),[]).append(r);codes[r['id']]=r
    return names,codes,{r['state'] for r in rows}

@lru_cache(maxsize=8192)
def resolve(source):
    text=re.sub(r'\s+',' ',core.norm(source));text=re.sub(r'^atc(?:\s+|\s*[-:/]\s*)','',text).strip()
    names,codes,ufs=reference();state=None
    if text.upper() in ufs:return ['',text.upper(),'BR','UF explícita na origem']
    match=re.search(r'(?:\s*[/,-]\s*|\s+|\s*\()([a-z]{2})\)?$',text)
    if match and match.group(1).upper() in ufs:
        state=match.group(1).upper();text=text[:match.start()].strip()
    hits=[codes[text]] if text in codes else names.get(text,[])
    if not hits:
        # An explicit UF establishes Brazil/state, but not a municipality.
        return ['',state or '', 'BR' if state else '', 'UF explícita; município não reconhecido' if state else 'Origem não reconhecida']
    filtered=[r for r in hits if not state or r['state']==state]
    if state and not filtered:return ['','','','Município e UF informados são incompatíveis']
    if len(filtered)==1:
        r=filtered[0];return [core.norm(r['name']),r['state'],'BR','Correspondência exata no cadastro IBGE distribuído; código '+r['id']]
    states={r['state'] for r in filtered}
    return ['',next(iter(states)) if len(states)==1 else '', 'BR','Nome brasileiro homônimo; município/UF ambíguos']

def resolve_json(source):return json.dumps(resolve(source),ensure_ascii=False)

def prepare(c,data):
    c.create_function('resolve_locality',1,resolve_json,deterministic=True)
    if c.execute('PRAGMA user_version').fetchone()[0]>=5:return
    reference()  # Check integrity before any change.
    folder=data/'backups';folder.mkdir(exist_ok=True)
    with sqlite3.connect(folder/('antes-migracao-v5-'+uuid4().hex+'.sqlite3')) as backup:
        c.backup(backup)
        if backup.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('Backup inválido; migração v5 cancelada.')
    try:
        c.execute('BEGIN IMMEDIATE')
        if c.execute('PRAGMA user_version').fetchone()[0]>=5:c.commit();return
        c.execute('CREATE TABLE automatic_localities(source TEXT PRIMARY KEY,municipality TEXT,state TEXT,country TEXT,evidence TEXT)')
        # Repair only the derived locality source for legacy unmapped Cidade/ATC headers.
        c.execute("UPDATE holiday_identity_records SET source=(SELECT json_extract(holiday_identity(r.raw,i.mapping),'$[2]') FROM records r JOIN imports i ON i.id=r.import_id WHERE r.id=holiday_identity_records.id)")
        projection="SELECT source,json_extract(resolve_locality(source),'$[0]'),json_extract(resolve_locality(source),'$[1]'),json_extract(resolve_locality(source),'$[2]'),json_extract(resolve_locality(source),'$[3]') FROM (SELECT DISTINCT source FROM holiday_identity_records)"
        c.execute('INSERT INTO automatic_localities '+projection)
        c.execute('CREATE TABLE import_brazil_proofs(import_id INTEGER PRIMARY KEY,evidence TEXT NOT NULL,confirmed_at TEXT NOT NULL)')
        c.execute("CREATE TRIGGER automatic_locality_insert AFTER INSERT ON holiday_identity_records WHEN NOT EXISTS(SELECT 1 FROM automatic_localities WHERE source=NEW.source) BEGIN INSERT INTO automatic_localities SELECT NEW.source,json_extract(resolve_locality(NEW.source),'$[0]'),json_extract(resolve_locality(NEW.source),'$[1]'),json_extract(resolve_locality(NEW.source),'$[2]'),json_extract(resolve_locality(NEW.source),'$[3]'); END")
        for event in ('INSERT','UPDATE','DELETE'):
            c.execute(f'CREATE TRIGGER brazil_proof_revision_{event} AFTER {event} ON import_brazil_proofs BEGIN UPDATE cache_revision SET revision=revision+1 WHERE id=1; END')
        c.execute('UPDATE cache_revision SET revision=revision+1 WHERE id=1');c.execute('PRAGMA user_version=5');c.commit()
    except Exception:c.rollback();raise

def prove_brazil(import_id,evidence):
    import storage
    if not evidence.strip():raise ValueError('Informe a evidência que comprova execução no Brasil.')
    with storage.connect() as c:
        c.execute('BEGIN IMMEDIATE')
        r=c.execute('SELECT month,name FROM imports WHERE id=?',(import_id,)).fetchone()
        if not r:raise ValueError('Importação não encontrada.')
        storage.ensure_open(c,r['month'])
        c.execute('INSERT INTO import_brazil_proofs VALUES(?,?,?) ON CONFLICT(import_id) DO UPDATE SET evidence=excluded.evidence,confirmed_at=excluded.confirmed_at',(import_id,evidence.strip(),storage.now()))
        c.execute('INSERT INTO audit(month,action,detail,created_at) VALUES(?,?,?,?)',(r['month'],'Comprovar execução no Brasil',json.dumps({'import_id':import_id,'arquivo':r['name'],'evidencia':evidence},ensure_ascii=False),storage.now()))
