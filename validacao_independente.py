"""Recálculo de originais em duas fases: entradas sem resultados e comparação posterior.

Não importa os motores financeiros do aplicativo. Execute com o Streamlit fechado.
"""
import argparse
from collections import Counter
from contextlib import closing
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import tempfile
import unicodedata
import openpyxl

KEYS=('138','128','137','impressao','apontamento','feriado')
METRICS=('u138','u128','u137','uprint','uop')
REFERENCE_SHA='72e96f8c4044bdba30397231a7695a36c9f4134b984f954d5fd65b22675f1702'


def norm(value):
    return ''.join(c for c in unicodedata.normalize('NFD',str(value if value is not None else '').strip().casefold()) if not unicodedata.combining(c))


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


def fingerprint(raw):
    return hashlib.sha256(json.dumps(raw,ensure_ascii=False,sort_keys=True).encode()).hexdigest()


def original_rows(path,sheet_name,headers):
    """Leitor próprio: não usa core, excel_io ou resultados armazenados."""
    if not headers or any(not h for h in headers) or len(set(headers))!=len(headers):
        raise ValueError('Cabeçalhos vazios/repetidos')
    book=openpyxl.load_workbook(path,read_only=True,data_only=False)
    try:
        sheet=book[sheet_name];sheet.reset_dimensions();found=False
        for line,values in enumerate(sheet.iter_rows(values_only=True),1):
            if not found:
                names=[str(v).strip() if v is not None else '' for v in values]
                if names==headers:found=True
                elif line>=40:raise ValueError('Cabeçalhos não conferem com a importação')
                continue
            if not any(v not in (None,'') for v in values):continue
            if any(v is not None for v in values[len(headers):]):raise ValueError('Dados fora dos cabeçalhos')
            raw={h:(values[i].isoformat() if isinstance(values[i],(datetime,date)) else values[i]) if i<len(values) else None for i,h in enumerate(headers)}
            yield {'line':line,'raw':raw}
        if not found:raise ValueError('Cabeçalhos não encontrados')
    finally:book.close()


def day(value):
    if not isinstance(value,str) or not value.strip():return None
    try:return datetime.strptime(value.strip(),'%d/%m/%Y').date().isoformat()
    except ValueError:
        try:return datetime.fromisoformat(value.strip()).date().isoformat()
        except ValueError:return None


def five(raw,mapping,month):
    """Implementação independente dos cinco critérios e validações existentes."""
    get=lambda k:raw.get(mapping.get(k))
    printed,retained,cause=map(norm,(get('printed'),get('retained'),get('cause')))
    units=dict.fromkeys(KEYS,0);errors=[]
    required=('printed','retained','cause','copies','operational')
    if any(isinstance(get(k),str) and get(k).startswith('=') for k in required):errors.append('Fórmula em coluna financeira')
    if retained not in ('sim','nao'):errors.append('Fatura Retida inválida')
    if printed not in ('sim','nao'):errors.append('Faturas Impressas inválida')
    if retained=='nao':
        if cause:units['137']=1
        elif printed=='sim':units['138']=1
        elif printed=='nao':units['128']=1
    try:
        number=Decimal(str(get('copies')).strip().replace(',','.')) if norm(get('copies')) else Decimal(0)
        if not number.is_finite() or number<0 or number!=number.to_integral_value():raise ValueError()
        units['impressao']=int(number)
    except (InvalidOperation,ValueError):errors.append('Comunicados: inteiro não negativo exigido')
    units['apontamento']=int(bool(norm(get('operational'))))
    value=get('date');actual=None
    if norm(value):
        actual='inválida'
        for fmt in ('%d/%m/%Y','%Y-%m-%d','%Y-%m-%dT%H:%M:%S'):
            try:actual=datetime.strptime(str(value),fmt).strftime('%Y-%m');break
            except ValueError:pass
    if mapping.get('date') and actual is not None and actual!=month:errors.append('Data inválida ou fora do mês')
    if errors:units=dict.fromkeys(KEYS,0)
    return units,errors


class Rows:
    def __init__(self,book,title,headers):
        self.book=book;self.title=title;self.headers=headers;self.count=0;self.index=1
        self.sheet=book.create_sheet(title[:26]+' 1');self.write(headers)
    def append(self,values):
        if self.count>=1048575:
            self.index+=1;self.sheet=self.book.create_sheet(self.title[:26]+' '+str(self.index));self.count=0
            self.write(self.headers)
        self.write(values);self.count+=1
    def write(self,values):
        cells=[]
        for value in values:
            cell=openpyxl.cell.WriteOnlyCell(self.sheet,value=value)
            if isinstance(value,str):cell.data_type='s'
            cells.append(cell)
        self.sheet.append(cells)


def ro(data):
    c=sqlite3.connect((Path(data).resolve()/'contrato.sqlite3').as_uri()+'?mode=ro',uri=True)
    c.row_factory=sqlite3.Row;c.execute('PRAGMA busy_timeout=30000');c.execute('BEGIN')
    if c.execute('PRAGMA user_version').fetchone()[0]!=5:c.close();raise ValueError('Exige schema 5; não executa migrações.')
    return c


def export_inputs(data,output,month):
    """Consulta apenas configuração, proveniência e exclusões. Não lê resultados."""
    with closing(ro(data)) as c:
        info=c.execute('SELECT prices,closed FROM months WHERE month=?',(month,)).fetchone()
        if not info:raise ValueError('Mês não disponível nesta base. Nenhum resultado foi calculado.')
        imports=[dict(r) for r in c.execute('SELECT id,name,sha,sheet,mapping,headers,created_at,deleted FROM imports WHERE month=? ORDER BY id',(month,))]
        excluded=output/'exclusoes.jsonl'
        with excluded.open('w',encoding='utf-8') as f:
            for r in c.execute('SELECT fingerprint,reason FROM records WHERE month=? AND excluded<>0 AND import_deleted=0',(month,)):
                f.write(json.dumps(dict(r),ensure_ascii=False)+'\n')
        refs=Path(__file__).parent/'reference_data'
        for name in ('municipalities.json','municipal_confirmations.json'):(output/name).write_bytes((refs/name).read_bytes())
        manifest={'format':1,'month':month,'closed':bool(info['closed']),'prices':json.loads(info['prices'])|{'feriado':105},
            'revision':c.execute('SELECT revision FROM cache_revision WHERE id=1').fetchone()[0],
            'originals':str(Path(data).resolve()/'originais'),'imports':imports,
            'holidays':[dict(r) for r in c.execute('SELECT day,description,scope,state,municipality FROM holidays ORDER BY day,scope,state,municipality')],
            'bindings':[dict(r) for r in c.execute('SELECT source,municipality,state FROM municipality_bindings')],
            'brazil_proofs':[dict(r) for r in c.execute('SELECT import_id,evidence,confirmed_at FROM import_brazil_proofs')],
            'exclusions_sha':sha(excluded),'municipalities_sha':sha(output/'municipalities.json'),
            'confirmations_sha':sha(output/'municipal_confirmations.json')}
        (output/'entradas.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return output/'entradas.json'


class Geography:
    def __init__(self,manifest,folder):
        if sha(folder/'municipalities.json')!=REFERENCE_SHA:raise ValueError('Referência IBGE não confere')
        names={};self.codes={};self.ufs=set();self.cache={}
        for r in json.loads((folder/'municipalities.json').read_text(encoding='utf-8')):
            names.setdefault(norm(r['name']),[]).append(r);self.codes[r['id']]=r;self.ufs.add(r['state'])
        self.names=names;self.bindings={norm(r['source']):r for r in manifest['bindings']}
        self.confirmations={}
        for r in json.loads((folder/'municipal_confirmations.json').read_text(encoding='utf-8')):
            hit=self.codes.get(r['ibge_id'])
            if not hit or hit['state']!=r['state'] or r['scope']!='Municipal' or not r['evidence'].strip():raise ValueError('Confirmação municipal inválida')
            self.confirmations[norm(r['source'])]=(norm(hit['name']),hit['state'],r['evidence'])
    def automatic(self,source):
        if source in self.cache:return self.cache[source]
        text=re.sub(r'\s+',' ',source);text=re.sub(r'^atc(?:\s+|\s*[-:/]\s*)','',text).strip();uf=''
        if text.upper() in self.ufs:return ('',text.upper(),'BR','UF explícita')
        match=re.search(r'(?:\s*[/,-]\s*|\s+|\s*\()([a-z]{2})\)?$',text)
        if match and match.group(1).upper() in self.ufs:uf=match.group(1).upper();text=text[:match.start()].strip()
        hits=[self.codes[text]] if text in self.codes else self.names.get(text,[])
        filtered=[r for r in hits if not uf or r['state']==uf]
        if not hits:result=('',uf,'BR' if uf else '','Município não identificado')
        elif uf and not filtered:result=('','','','Município/UF incompatíveis')
        elif len(filtered)==1:result=(norm(filtered[0]['name']),filtered[0]['state'],'BR','IBGE '+filtered[0]['id'])
        else:
            states={r['state'] for r in filtered};result=('',next(iter(states)) if len(states)==1 else '','BR','Homônimo brasileiro')
        if len(self.cache)>=8192:self.cache.clear()
        self.cache[source]=result;return result
    def resolve(self,source,calendar,proof):
        town,uf,country,evidence=self.automatic(source)
        binding=self.bindings.get(source)
        confirmation=self.confirmations.get(source) if any(h['scope']=='Municipal' for h in calendar) and not any(h['scope'] in ('Nacional','Estadual') for h in calendar) else None
        if confirmation and not binding:town,uf,evidence=confirmation
        if binding:
            town=norm(binding['municipality']) or town;uf=binding['state'] or uf;country='BR';evidence='Confirmação cadastral explícita'
        if proof:country='BR';evidence+='; Brasil: '+proof
        return town,uf,country,evidence


def fee_status(raw,mapping,calendar,geo,proof):
    get=lambda k:raw.get(mapping.get(k));d=day(get('date'))
    source=norm(get('city'))
    if not mapping.get('city'):
        values={norm(v) for k,v in raw.items() if norm(k) in ('cidade/atc','cidade / atc','atc','cidade','municipio') and norm(v)}
        source=next(iter(values)) if len(values)==1 else ('__colunas_municipais_divergentes__' if values else '')
    hs=calendar.get(d,[]);town,uf,country,evidence=geo.resolve(source,hs,proof)
    supply=str(get('supply') or '').strip();execution=str(get('task') or '').strip()
    if not d:status='Sem data válida: feriado não verificável'
    elif date.fromisoformat(d).weekday()==6:status='Domingo: conferir'
    elif norm(get('retained'))!='nao':status='Fatura Retida diferente de Não'
    elif norm(get('cause')):status='Causa preenchida'
    elif not hs:status='Sem feriado cadastrado nesta data'
    elif not supply or not execution:status='Fornecimento/execução ausente'
    elif any((h['scope']=='Nacional' and country=='BR') or (h['scope']=='Estadual' and uf and h['state']==uf) or
             (h['scope']=='Municipal' and uf and town and h['state']==uf and norm(h['municipality'])==town) for h in hs):status='Elegível'
    elif any(h['scope']=='Nacional' for h in hs) and country!='BR':status='Execução no Brasil não comprovada'
    elif any(h['scope']=='Estadual' for h in hs) and not uf:status='UF não confirmada'
    elif any(h['scope']=='Municipal' for h in hs) and not any(h['scope']=='Municipal' and (not uf or h['state']==uf) and (not town or norm(h['municipality'])==town) for h in hs):status='Não aplicável — outro município'
    elif any(h['scope']=='Municipal' for h in hs) and (not town or not uf):status='Município/UF não confirmado'
    else:status='Não aplicável'
    return d,supply,execution,town,uf,country,evidence,status


def calculate(manifest_path,scratch):
    """Não recebe conexão de produção, totais anteriores ou quantidades esperadas."""
    manifest_path=Path(manifest_path);folder=manifest_path.parent
    m=json.loads(manifest_path.read_text(encoding='utf-8'));month=m['month'];date.fromisoformat(month+'-01')
    for filename,key in [('exclusoes.jsonl','exclusions_sha'),('municipalities.json','municipalities_sha'),('municipal_confirmations.json','confirmations_sha')]:
        if sha(folder/filename)!=m[key]:raise ValueError('Entrada alterada: '+filename)
    geo=Geography(m,folder);calendar={}
    for h in m['holidays']:calendar.setdefault(h['day'],[]).append(h)
    proofs={r['import_id']:r['evidence'] for r in m['brazil_proofs']}
    scratch.executescript("CREATE TABLE exclusions(fp TEXT PRIMARY KEY,reason TEXT);\n        CREATE TABLE calculations(seq INTEGER PRIMARY KEY,fp TEXT,import_id INTEGER,line INTEGER,raw TEXT,mapping TEXT,\n        u138 INTEGER,u128 INTEGER,u137 INTEGER,uprint INTEGER,uop INTEGER,fee INTEGER,\n        day TEXT,supply TEXT,execution TEXT,town TEXT,uf TEXT,country TEXT,evidence TEXT,fee_reason TEXT,\n        disposition TEXT,errors TEXT,date_class TEXT);\n        CREATE UNIQUE INDEX accepted_fp ON calculations(fp) WHERE disposition='Ativo';\n        CREATE INDEX execution_group ON calculations(day,supply,execution,fee_reason);\n        CREATE INDEX calculation_fp ON calculations(fp);")
    with (folder/'exclusoes.jsonl').open(encoding='utf-8') as f:
        for line in f:
            r=json.loads(line);scratch.execute('INSERT OR REPLACE INTO exclusions VALUES(?,?)',(r['fingerprint'],r['reason']))
    inventory=[]
    for entry in m['imports']:
        if entry['deleted']:inventory.append({'id':entry['id'],'name':entry['name'],'excluded_import':True});continue
        digest=entry['sha']
        if not re.fullmatch('[0-9a-f]{64}',digest):raise ValueError('SHA de original inválido')
        path=Path(m['originals'])/(digest+'.xlsx')
        if sha(path)!=digest:raise ValueError('Original não confere: '+entry['name'])
        mapping=json.loads(entry['mapping']);headers=json.loads(entry['headers'])
        if any(not mapping.get(k) for k in ('printed','retained','cause','copies','operational')):raise ValueError('Mapeamento obrigatório ausente')
        mapped=[v for v in mapping.values() if v]
        if len(set(mapped))!=len(mapped) or any(v not in headers for v in mapped):raise ValueError('Mapeamento incompatível com os cabeçalhos')
        count=0
        for row in original_rows(path,entry['sheet'],headers):
            count+=1;raw=row['raw'];fp=fingerprint(raw);units,errors=five(raw,mapping,month)
            excluded=scratch.execute('SELECT reason FROM exclusions WHERE fp=?',(fp,)).fetchone()
            duplicate=scratch.execute('SELECT seq FROM calculations WHERE fp=?',(fp,)).fetchone()
            disposition='Duplicata integral do original' if duplicate else 'Exclusão lógica registrada' if excluded else 'Ativo'
            d,supply,execution,town,uf,country,evidence,status=fee_status(raw,mapping,calendar,geo,proofs.get(entry['id'],''))
            value=raw.get(mapping.get('date'))
            dc=('Coluna de data não mapeada' if not mapping.get('date') else 'Data vazia: mês apenas pela importação' if not norm(value) else
                'Data inválida/não reconhecida' if d is None else 'Data fora do mês de referência' if d[:7]!=month else 'Data no mês de referência')
            if disposition!='Ativo':units=dict.fromkeys(KEYS,0);status=disposition
            scratch.execute('INSERT INTO calculations VALUES('+','.join('?' for _ in range(23))+')',(
                None,fp,entry['id'],row['line'],json.dumps(raw,ensure_ascii=False),json.dumps(mapping),
                *[units[k] for k in KEYS],d,supply,execution,town,uf,country,evidence,status,disposition,json.dumps(errors,ensure_ascii=False),dc))
            if count%1000==0:scratch.commit();print(f'{entry["name"]}: {count} linhas recalculadas',flush=True)
        if sha(path)!=digest:raise ValueError('Original mudou durante a leitura')
        inventory.append({'id':entry['id'],'name':entry['name'],'sha':digest,'rows':count,'sha_verified':True})
    scratch.execute("UPDATE calculations SET fee_reason='Execução com localidades divergentes' WHERE fee_reason='Elegível' AND (day,supply,execution) IN (SELECT day,supply,execution FROM calculations WHERE fee_reason='Elegível' GROUP BY day,supply,execution HAVING COUNT(DISTINCT town||'/'||uf)>1)")
    scratch.execute("UPDATE calculations SET fee=1 WHERE seq IN (SELECT MIN(seq) FROM calculations WHERE fee_reason='Elegível' GROUP BY day,supply,execution)")
    scratch.execute("UPDATE calculations SET fee_reason='Duplicata de execução de feriado' WHERE fee_reason='Elegível' AND fee=0")
    scratch.commit()
    sums=scratch.execute('SELECT '+','.join('COALESCE(SUM('+v+'),0)' for v in (*METRICS,'fee'))+' FROM calculations').fetchone()
    q=dict(zip(KEYS,sums));result={'month':month,'prices':m['prices'],'independent_quantities':q,
        'independent_total_cents':sum(q[k]*m['prices'][k] for k in KEYS),'originals':inventory,
        'date_classes':dict(scratch.execute('SELECT date_class,COUNT(*) FROM calculations GROUP BY date_class')),
        'active_missing_date':scratch.execute("SELECT COUNT(*) FROM calculations WHERE disposition='Ativo' AND day IS NULL").fetchone()[0],
        'active_date_classes':dict(scratch.execute("SELECT date_class,COUNT(*) FROM calculations WHERE disposition='Ativo' GROUP BY date_class")),
        'missing_date_attribution':{'confirmed_by_reading_date':0,
            'criterion':'Sem data não se comprova a ocorrência no mês por esta coluna. Inclusão financeira mantém a associação documental da importação, sem inventar uma data.',
            'quantities_in_monthly_by_import_provenance':dict(zip(KEYS,scratch.execute('SELECT '+','.join('COALESCE(SUM('+v+'),0)' for v in (*METRICS,'fee'))+" FROM calculations WHERE disposition='Ativo' AND day IS NULL").fetchone()))},
        'manifest_sha256':sha(manifest_path),'calculation_completed_before_comparison':True}
    (folder/'calculo_independente.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    return m,result


def compare(data,m,result,scratch,details=True):
    """Só depois do cálculo: feriados uma vez, em tabela temporária indexada."""
    import holidays
    from time import perf_counter
    began=perf_counter();last_message=began;stage='Preparando comparação';timings={}
    def progress():
        nonlocal last_message
        now=perf_counter()
        if now-last_message>=2:
            print(f'{stage}: SQL em execução ({now-began:.1f}s desde o início)...',flush=True)
            last_message=now
        return 0
    def announce(message):
        nonlocal stage,last_message
        stage=message;last_message=perf_counter();print(message,flush=True)
    with closing(ro(data)) as c:
        c.set_progress_handler(progress,100000)
        revision=c.execute('SELECT revision FROM cache_revision WHERE id=1').fetchone()[0]
        if revision!=m['revision']:raise ValueError('A base mudou desde a exportação das entradas; comparação cancelada sem alterar o cálculo salvo.')
        info=c.execute('SELECT prices FROM months WHERE month=?',(m['month'],)).fetchone()
        if not info or json.loads(info['prices'])!={k:m['prices'][k] for k in KEYS[:-1]}:raise ValueError('Os preços de entrada e da base diferem')
        imports=[dict(r) for r in c.execute('SELECT id,name,sha,sheet,mapping,headers,created_at,deleted FROM imports WHERE month=? ORDER BY id',(m['month'],))]
        if imports!=m['imports']:raise ValueError('As importações não correspondem ao manifesto salvo; confira o caminho da base.')
        announce('1/4 Somando os cinco serviços no banco, somente leitura')
        tick=perf_counter()
        sums=c.execute('SELECT '+','.join('COALESCE(SUM('+v+'),0)' for v in METRICS)+
            ' FROM record_metrics WHERE month=? AND excluded=0 AND import_deleted=0',(m['month'],)).fetchone()
        units=dict(zip(KEYS[:-1],sums));timings['five_services_seconds']=perf_counter()-tick
        announce('2/4 Apurando IDs de feriado uma única vez (calendário/fechamento preservados)')
        tick=perf_counter();fee_sql,args=holidays.charges_query(c,m['month'])
        scratch.execute('CREATE TABLE charged_ids(id INTEGER PRIMARY KEY)')
        batch=[];fee_count=0
        for row in c.execute('SELECT id FROM ('+fee_sql+')',args):
            batch.append((row[0],));fee_count+=1
            if len(batch)>=1000:scratch.executemany('INSERT INTO charged_ids VALUES(?)',batch);batch=[]
            if fee_count%10000==0:print(f'Feriados identificados: {fee_count:,}',flush=True)
        if batch:scratch.executemany('INSERT INTO charged_ids VALUES(?)',batch)
        units['feriado']=fee_count;timings['holiday_ids_seconds']=perf_counter()-tick
        announce(f'Feriados identificados: {fee_count:,}. Consulta de feriados concluída.')
        detail_matches=None;rows=0
        if details:
            announce('3/4 Transferindo registros em lotes, sem juntar o calendário a cada linha')
            tick=perf_counter()
            scratch.execute('CREATE TABLE app(fp TEXT PRIMARY KEY,id INTEGER,import_id INTEGER,line INTEGER,u138 INTEGER,u128 INTEGER,u137 INTEGER,uprint INTEGER,uop INTEGER,fee INTEGER)')
            sql="""SELECT r.fingerprint,r.id,r.import_id,r.line,
                CASE WHEN m.excluded=0 AND m.import_deleted=0 THEN m.u138 ELSE 0 END,
                CASE WHEN m.excluded=0 AND m.import_deleted=0 THEN m.u128 ELSE 0 END,
                CASE WHEN m.excluded=0 AND m.import_deleted=0 THEN m.u137 ELSE 0 END,
                CASE WHEN m.excluded=0 AND m.import_deleted=0 THEN m.uprint ELSE 0 END,
                CASE WHEN m.excluded=0 AND m.import_deleted=0 THEN m.uop ELSE 0 END,0
                FROM records r LEFT JOIN record_metrics m ON m.id=r.id
                WHERE r.month=? AND r.import_deleted=0 ORDER BY r.id"""
            batch=[]
            for row in c.execute(sql,(m['month'],)):
                batch.append(tuple(row));rows+=1
                if len(batch)>=1000:scratch.executemany('INSERT INTO app VALUES(?,?,?,?,?,?,?,?,?,?)',batch);batch=[]
                if rows%10000==0:print(f'Registros transferidos: {rows:,} ({perf_counter()-tick:.1f}s)',flush=True)
            if batch:scratch.executemany('INSERT INTO app VALUES(?,?,?,?,?,?,?,?,?,?)',batch)
            timings['record_transfer_seconds']=perf_counter()-tick
            announce('4/4 Conferindo feriados por índice no banco temporário e conciliando somas')
            tick=perf_counter()
            scratch.execute('CREATE INDEX app_id ON app(id)')
            scratch.execute('UPDATE app SET fee=1 WHERE id IN (SELECT id FROM charged_ids)')
            detail_sums=scratch.execute('SELECT '+','.join('COALESCE(SUM('+v+'),0)' for v in (*METRICS,'fee'))+' FROM app').fetchone()
            detail_matches=all(detail_sums[i]==units[k] for i,k in enumerate(KEYS))
            timings['indexed_join_and_sum_seconds']=perf_counter()-tick
        else:announce('3/4 e 4/4 Comparação agregada: usando as seis quantidades já salvas, sem ler Excel')
        result['comparison']={'app_quantities':units,'app_total_cents':sum(units[k]*m['prices'][k] for k in KEYS),
            'delta_quantities':{k:result['independent_quantities'][k]-units[k] for k in KEYS},
            'delta_cents':result['independent_total_cents']-sum(units[k]*m['prices'][k] for k in KEYS),
            'app_details_match_aggregates':detail_matches,'detail_comparison_available':details,
            'app_records_transferred':rows,'timings':timings,
            'limits':['O SQL do aplicativo é consultado somente nesta etapa. Não influenciou as quantidades independentes.',
                      'Se o mês foi congelado e o calendário foi alterado depois, a referência pode manter feriados históricos. O recálculo usa o calendário exportado, sem copiar cobranças congeladas.']}
        c.set_progress_handler(None,0)
    scratch.commit()
    timings['comparison_total_seconds']=perf_counter()-began
    print(f'Comparação concluída em {timings["comparison_total_seconds"]:.2f}s.',flush=True)


def reports(output,m,result,scratch,has_comparison):
    print('Gerando relatórios detalhados dos originais...',flush=True)
    book=openpyxl.Workbook(write_only=True)
    headers=['Sequência independente','ID no aplicativo','Importação','Arquivo','Aba','Linha original','Fingerprint','Situação',
             'Grupo','Cidade/ATC','Município','UF','Evidência localidade','Funcionário','Fornecimento','Execução','Data original',
             'Data interpretada','Classificação da data','Erros independentes','Motivo feriado',
             'Fatura Retida','Faturas Impressas','Causa','Comunicados originais','CO1 Atual',*KEYS,'Total independente (centavos)']
    all_rows=Rows(book,'Registros originais',headers);dateless=Rows(book,'Sem data válida',headers)
    fee_rows=Rows(book,'Feriados',headers)
    differences=Rows(book,'Divergências',headers+['Motivo comparação',*['App '+k for k in KEYS],*['Diferença '+k for k in KEYS],'Diferença (centavos)'])
    source={r['id']:r for r in m['imports']}
    select='SELECT x.*'+(',a.id app_id,'+','.join('a.'+v+' app_'+v for v in (*METRICS,'fee')) if has_comparison else '')+' FROM calculations x'
    if has_comparison:select+=' LEFT JOIN app a ON a.fp=x.fp'
    counts=Counter();delta_sum=Counter();different=0;checks=Counter()
    for r in scratch.execute(select+' ORDER BY x.seq'):
        raw=json.loads(r['raw']);mapping=json.loads(r['mapping']);get=lambda k:raw.get(mapping.get(k));entry=source[r['import_id']]
        units=[r[v] for v in (*METRICS,'fee')];total=sum(units[i]*m['prices'][k] for i,k in enumerate(KEYS))
        values=[r['seq'],r['app_id'] if has_comparison else None,r['import_id'],entry['name'],entry['sheet'],r['line'],r['fp'],r['disposition'],
            get('group'),get('city'),r['town'],r['uf'],r['evidence'],get('employee'),r['supply'],r['execution'],get('date'),r['day'],r['date_class'],
            '; '.join(json.loads(r['errors'])),r['fee_reason'],get('retained'),get('printed'),get('cause'),get('copies'),get('operational'),*units,total]
        all_rows.append(values)
        if r['disposition']=='Ativo':
            retained=norm(get('retained'));cause=norm(get('cause'))
            checks['Registros retida='+retained]+=1
            checks['Causa preenchida' if cause else 'Causa vazia']+=1
            if retained=='sim':
                checks['Leituras cobradas em retidas']+=sum(units[:3])
                checks['Impressão cobrada em retidas']+=units[3]
                checks['Apontamentos cobrados em retidas']+=units[4]
            checks['Comunicados cobrados']+=units[3]
            checks['Apontamentos cobrados']+=units[4]
        if r['day'] is None:dateless.append(values)
        fee_rows.append(values)  # Includes noncharged/undated records, preserving all reasons.
        counts[r['fee_reason']]+=1
        if r['seq']%10000==0:print(f'Linhas exportadas para Excel: {r["seq"]:,}',flush=True)
        # Full duplicates have zero contribution and are explained in Registros originais.
        if has_comparison and r['disposition']!='Duplicata integral do original':
            other=[r['app_'+v] or 0 for v in (*METRICS,'fee')]
            delta=[a-b for a,b in zip(units,other)]
            if any(delta) or r['app_id'] is None:
                reason='Original sem registro correspondente no aplicativo' if r['app_id'] is None else 'Unidades divergem; conferir erros, situação e elegibilidade detalhados'
                differences.append(values+[reason,*other,*delta,sum(delta[i]*m['prices'][k] for i,k in enumerate(KEYS))]);different+=1
            delta_sum.update(dict(zip(KEYS,delta)))
    if has_comparison:
        for r in scratch.execute("SELECT a.* FROM app a WHERE NOT EXISTS(SELECT 1 FROM calculations x WHERE x.fp=a.fp AND x.disposition<>'Duplicata integral do original')"):
            other=[r[v] for v in (*METRICS,'fee')];delta=[-v for v in other]
            values=[None,r['id'],r['import_id'],None,None,r['line'],r['fp'],'Registro do aplicativo ausente nos originais selecionados']+[None]*(len(headers)-8)
            differences.append(values+['Sem original correspondente',*other,*delta,sum(delta[i]*m['prices'][k] for i,k in enumerate(KEYS))]);different+=1
            delta_sum.update(dict(zip(KEYS,delta)))
        result['comparison']['different_records']=different
        result['comparison']['detail_delta_matches_totals']=all(delta_sum[k]==result['comparison']['delta_quantities'][k] for k in KEYS)
    result['holiday_reasons']=dict(counts)
    result['commercial_crosschecks_active_unique']=dict(checks)
    summary=Rows(book,'Resumo seis serviços',['Serviço','Quantidade independente','Preço centavos','Total independente centavos','Quantidade aplicativo','Diferença quantidade','Diferença centavos'])
    for k in KEYS:
        q=result['independent_quantities'][k];app=result.get('comparison',{}).get('app_quantities',{}).get(k)
        summary.append([k,q,m['prices'][k],q*m['prices'][k],app,None if app is None else q-app,None if app is None else (q-app)*m['prices'][k]])
    reasons=Rows(book,'Motivos feriados',['Motivo','Registros'])
    for reason,n in sorted(counts.items()):reasons.append([reason,n])
    inputs=Rows(book,'Entradas e proveniência',['Campo','Valor'])
    for k,v in m.items():
        # Original metadata can be long; keep individual entries below Excel's cell limit.
        if isinstance(v,list):
            for i,entry in enumerate(v):inputs.append([k+' '+str(i+1),json.dumps(entry,ensure_ascii=False)])
        else:inputs.append([k,json.dumps(v,ensure_ascii=False)])
    book.save(output/'validacao.xlsx')
    result['limits']=['Sem data de leitura não é possível comprovar a data real apenas pelo mês escolhido na importação.',
        'Inclusão no acumulado por proveniência de importação segue a regra já existente; não é confirmação independente de setembro.',
        'Exclusões lógicas e associação dos arquivos ao mês são controles importados do manifesto, não resultados financeiros.',
        'Não usa quantidades manuais nem valores-alvo; todos os totais são somas das linhas dos originais.',
        'Mapeamentos, calendário e confirmações documentais são entradas configuradas, exportadas e auditáveis; não são revalidadas por uma fonte externa nesta execução.',
        'As contagens de datas incluem as linhas dos originais; active_missing_date considera apenas os fingerprints ativos únicos.',
        'A fórmula de feriado independe das cinco validações gerais, conforme o comportamento vigente; domingos não são cobrados automaticamente.']
    (output/'resultado.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'RELATORIO.md').write_text('# Validação independente dos originais\n\n'
        'As quantidades foram calculadas antes da consulta dos resultados do aplicativo. '
        'Nenhum resultado manual ou total anterior é entrada do recálculo.\n\n```json\n'+json.dumps(result,ensure_ascii=False,indent=2)+'\n```\n\n'
        'Consulte validacao.xlsx para registros, seis serviços, datas, feriados e divergências. '
        'calculo_independente.json foi gravado antes da comparação e não é sobrescrito por ela.\n',encoding='utf-8')


def compare_saved(data,folder,output):
    """Retoma JSON legado: somente seis agregados; nenhum Excel é aberto."""
    folder=Path(folder).resolve();output=Path(output).resolve();data=Path(data).resolve()
    if output==data or data in output.parents or output==folder or folder in output.parents:
        raise ValueError('Use uma pasta de saída nova, fora de data e da validação original.')
    manifest=folder/'entradas.json';sealed=folder/'calculo_independente.json'
    m=json.loads(manifest.read_text(encoding='utf-8'));result=json.loads(sealed.read_text(encoding='utf-8'))
    if result.get('manifest_sha256')!=sha(manifest):raise ValueError('O manifesto não corresponde ao cálculo independente salvo.')
    if (result.get('month')!=m.get('month') or result.get('prices')!=m.get('prices') or
        result.get('calculation_completed_before_comparison') is not True):
        raise ValueError('O cálculo salvo está incompleto ou não corresponde às entradas.')
    q=result.get('independent_quantities',{})
    if (any(type(q.get(k)) is not int or q[k]<0 for k in KEYS) or
        type(result.get('independent_total_cents')) is not int or
        sum(q[k]*m['prices'][k] for k in KEYS)!=result['independent_total_cents']):
        raise ValueError('As quantidades, preços e total do JSON salvo não são consistentes.')
    source_hash=sha(sealed);output.mkdir(parents=True,exist_ok=False)
    result['resume']={'independent_file_sha256':source_hash,'manifest_sha256':sha(manifest),
        'reread_excel':False,'independent_file_overwritten':False,
        'scope':'Comparação agregada dos seis serviços. O JSON legado não contém as unidades independentes por registro.',
        'limits':'A interrupção da versão antiga removia o banco temporário de detalhes. IDs de divergências independentes não podem ser reconstruídos apenas do JSON, sem reler originais.'}
    with tempfile.TemporaryDirectory(prefix='sabesp-comparacao-') as temp,closing(sqlite3.connect(Path(temp)/'comparacao.sqlite3')) as scratch:
        scratch.row_factory=sqlite3.Row;compare(data,m,result,scratch,details=False)
    if sha(sealed)!=source_hash:raise ValueError('O cálculo independente foi alterado externamente durante a comparação.')
    book=openpyxl.Workbook(write_only=True)
    sheet=Rows(book,'Comparação seis serviços',['Serviço','Quantidade independente salva','Quantidade aplicativo',
        'Diferença quantidade','Preço centavos','Valor independente centavos','Valor aplicativo centavos','Diferença centavos'])
    for k in KEYS:
        a=q[k];b=result['comparison']['app_quantities'][k];price=m['prices'][k]
        sheet.append([k,a,b,a-b,price,a*price,b*price,(a-b)*price])
    notes=Rows(book,'Escopo e evidências',['Campo','Valor'])
    for k,v in result['resume'].items():notes.append([k,str(v)])
    book.save(output/'comparacao.xlsx')
    (output/'comparacao.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    (output/'RELATORIO_COMPARACAO.md').write_text('# Comparação do cálculo independente salvo\n\n'
        'Nenhum Excel foi relido e o cálculo original não foi sobrescrito. Comparação somente leitura no banco.\n\n'
        'Escopo: agregados por serviço. A ausência de diferença no total não comprova igualdade registro a registro.\n\n```json\n'+
        json.dumps({'resume':result['resume'],'comparison':result['comparison']},ensure_ascii=False,indent=2)+'\n```\n',encoding='utf-8')
    print(f'Comparação salva em {output}. Cálculo original preservado.',flush=True)
    return result


def run(output,data=None,manifest=None,month='2026-09',compare_app=True,previous_audit=None):
    output=Path(output).resolve()
    if bool(data)==bool(manifest):raise ValueError('Informe apenas --data ou --manifest.')
    if data:
        root=Path(data).resolve()
        if output==root or root in output.parents:raise ValueError('Saída deve ficar fora de data.')
    if manifest:
        original=json.loads(Path(manifest).read_text(encoding='utf-8'));root=Path(original['originals']).resolve()
        if output==root or root in output.parents or output==root.parent or root.parent in output.parents:raise ValueError('Saída deve ficar fora da pasta de dados e dos originais.')
    output.mkdir(parents=True,exist_ok=False)
    if data:manifest=export_inputs(data,output,month)
    else:
        original_folder=Path(manifest).resolve().parent
        for name in ('entradas.json','exclusoes.jsonl','municipalities.json','municipal_confirmations.json'):
            source=Path(manifest) if name=='entradas.json' else original_folder/name
            (output/name).write_bytes(source.read_bytes())
        manifest=output/'entradas.json'
    with tempfile.TemporaryDirectory(prefix='sabesp-independente-') as temp,closing(sqlite3.connect(Path(temp)/'calculo.sqlite3')) as scratch:
        scratch.row_factory=sqlite3.Row
        m,result=calculate(manifest,scratch)
        print('Recálculo independente concluído e gravado. Iniciando comparação, se solicitada.',flush=True)
        if data and compare_app:compare(data,m,result,scratch)
        if previous_audit:
            previous=json.loads(Path(previous_audit).read_text(encoding='utf-8'))
            if previous.get('month')!=m['month'] or not previous.get('available'):raise ValueError('Auditoria anterior não corresponde ao mês ou não tem dados reais')
            q=previous.get('official_quantities');total=previous.get('official_total_cents')
            if not isinstance(q,dict) or any(type(q.get(k)) is not int for k in KEYS) or type(total) is not int:raise ValueError('JSON de auditoria anterior incompatível')
            result['previous_audit_comparison']={'source_sha256':sha(previous_audit),'previous_total_cents':total,
                'delta_cents':result['independent_total_cents']-total,
                'delta_quantities':{k:result['independent_quantities'][k]-q[k] for k in KEYS},
                'limits':'Comparação agregada posterior; o JSON anterior não contém identificação individual de todos os registros.'}
        reports(output,m,result,scratch,bool(data and compare_app))
    print('Validação concluída. Nenhum dado de produção alterado. Saída:',output,flush=True)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--data');g.add_argument('--manifest');p.add_argument('--month',default='2026-09');p.add_argument('--output',required=True)
    p.add_argument('--sem-comparacao',action='store_true',help='Não consulta resultados do aplicativo, nem depois do cálculo.')
    p.add_argument('--auditoria-anterior',help='resultado.json da auditoria anterior; lido somente depois do recálculo.')
    p.add_argument('--somente-comparacao',metavar='PASTA',help='Reutiliza entradas.json e calculo_independente.json; não relê Excel.')
    a=p.parse_args()
    if a.somente_comparacao:
        if not a.data or a.sem_comparacao or a.auditoria_anterior:p.error('--somente-comparacao exige --data e não aceita --sem-comparacao/--auditoria-anterior.')
        compare_saved(a.data,a.somente_comparacao,a.output)
    else:run(a.output,a.data,a.manifest,a.month,not a.sem_comparacao,a.auditoria_anterior)
