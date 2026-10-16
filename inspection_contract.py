"""Escopo e critérios exclusivos de Vistorias, versionados por competência."""
import json,sqlite3,unicodedata
from pathlib import Path
from contextlib import closing

ALLOWED=['AGUDOS','ALAMBARI','ALUMINIO','ANHEMBI','ARACARIGUAMA','AREALVA','AREIOPOLIS','BOCAINA','BOFETE','BOITUVA','BORACEIA','BOTUCATU','CAPELA DO ALTO','CESARIO LANGE','CONCHAS','DOURADO','IBIUNA','IPERO','LARANJAL PAULISTA','PEDERNEIRAS','PEREIRAS','PIEDADE','PORANGABA','QUADRA','SALTO DE PIRAPORA','SAO MANUEL','SAO ROQUE','SARAPUI','TATUI','TORRE DE PEDRA','TORRINHA']
EXCLUDED=['ARACOIABA DA SERRA','MACATUBA']
MODES={'200014105':'once','200014106':'manual','200014104':'manual'}
LABELS={'once':'Cobrar uma vez por número de OS','execution':'Cobrar por execução realizada','manual':'Enviar OS repetidas para conferência manual'}

def norm(v):return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',str(v or '')) if not unicodedata.combining(c)).upper().split())

def initial(month):
    if month<'2026-09':return {'allowed':[],'excluded':[],'modes':MODES.copy(),'legacy':False,'effective':None}
    return {'allowed':ALLOWED.copy(),'excluded':EXCLUDED.copy(),'modes':MODES.copy(),'legacy':False,'effective':'2026-09'}

def policy(c,month,historical=True):
    if historical and c is not None:
        old=c.execute('SELECT payload FROM approvals WHERE month=?',(month,)).fetchone()
        if old:
            p=json.loads(old[0])
            # Aprovações antigas conservam critérios vigentes antes da implantação do escopo.
            return p.get('policy',{'allowed':[],'excluded':[],'modes':{k:'manual' for k in MODES},'legacy':True,'effective':None})
    p=initial(month)
    if c is None:return p
    scopes=[];modes=[]
    for key,value in c.execute("SELECT key,value FROM metadata WHERE key LIKE 'contract_scope:%' OR key LIKE 'billing_mode:%'"):
        v=json.loads(value)
        if v['effective']<=month:(scopes if key.startswith('contract_scope:') else modes).append(v)
    if scopes:
        v=max(scopes,key=lambda v:v['effective']);p.update(allowed=v['allowed'],excluded=v['excluded'],effective=v['effective'])
    for v in sorted(modes,key=lambda v:v['effective']):p['modes'][v['code']]=v['mode']
    return p

def from_root(root,month):
    bank=Path(root).resolve()/'financeiro.sqlite3'
    if not bank.exists():return initial(month)
    with closing(sqlite3.connect(bank.as_uri()+'?mode=ro',uri=True)) as c:return policy(c,month)

def classify(city,p):
    if p.get('legacy'):return 'Dentro do escopo'
    city=norm(city)
    if city in p['allowed']:return 'Dentro do escopo'
    if city in p['excluded']:return 'Fora do escopo do contrato'
    return 'Pendente: município não autorizado'
