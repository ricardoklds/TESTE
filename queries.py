"""Consultas SQL limitadas e agregadas sobre resultados já calculados."""
import json
from contextlib import closing
import core,storage

COLS={'138':'u138','128':'u128','137':'u137','impressao':'uprint','apontamento':'uop'}
LABELS={'employee':'Funcionário','city':'Unidade / cidade (ATC)','group_name':'Grupo'}

def revision():
    with closing(storage.connect()) as c:
        return c.execute('SELECT revision FROM cache_revision WHERE id=1').fetchone()[0]

def where(month,start=None,end=None,valid=False):
    text='m.month=?';args=[month]
    if start is not None:text+=' AND m.day BETWEEN ? AND ?';args.extend([start,end])
    if valid:text+=' AND m.excluded=0 AND m.import_deleted=0 AND m.errors=0'
    return text,args

def duplicates(month):
    return '''SELECT business_key FROM record_metrics WHERE month=? AND excluded=0 AND import_deleted=0
        AND business_key IS NOT NULL GROUP BY business_key HAVING COUNT(*)>1''',[month]

def overview(month,start=None,end=None):
    condition,args=where(month,start,end)
    valid=condition+' AND m.excluded=0 AND m.import_deleted=0'+(' AND m.errors=0' if start is not None else '')
    with closing(storage.connect()) as c:
        units=c.execute('SELECT '+','.join(f'COALESCE(SUM({v}),0) AS "{k}"' for k,v in COLS.items())+' FROM record_metrics m WHERE '+valid,args).fetchone()
        stats=c.execute('''SELECT COUNT(*) total_records,COUNT(DISTINCT import_id) import_count,
            COALESCE(SUM(excluded<>0 OR import_deleted<>0),0) excluded_count,
            COALESCE(SUM(excluded=0 AND import_deleted=0),0) active_count,
            COALESCE(SUM(excluded=0 AND import_deleted=0 AND errors=0),0) valid_count,
            COALESCE(SUM(excluded=0 AND import_deleted=0 AND errors>0),0) errors
            FROM record_metrics m WHERE '''+condition,args).fetchone()
        dup,dup_args=duplicates(month)
        extra=' AND day BETWEEN ? AND ?' if start is not None else ''
        conflicts=c.execute('SELECT COUNT(DISTINCT business_key) FROM record_metrics WHERE month=? AND excluded=0 AND import_deleted=0 AND business_key IN ('+dup+')'+extra,
                            [month,*dup_args,*([start,end] if start is not None else [])]).fetchone()[0]
        undated=c.execute('SELECT COUNT(*) FROM record_metrics WHERE month=? AND day IS NULL',(month,)).fetchone()[0]
    return {**dict(stats),'units':dict(units),'conflicts':conflicts,'undated':undated}

def summary(stats,prices):
    result=[{'Código':code,'Categoria':label,'Quantidade':stats['units'][k],'unit_cents':prices[k],
             'total_cents':stats['units'][k]*prices[k],'key':k} for k,(code,label,_) in core.CATEGORIES.items()]
    if 'holiday_quantity' in stats:
        result.append({'Código':'200014097','Categoria':'Adicional de leitura em feriado','Quantidade':stats['holiday_quantity'],
                       'unit_cents':105,'total_cents':stats['holiday_quantity']*105,'key':'feriado'})
    return result

def productivity(month,prices,by,start=None,end=None):
    column={'employee':'employee','city':'city','group':'group_name'}[by]
    condition,args=where(month,start,end,valid=start is not None)
    if start is None:condition+=' AND m.excluded=0 AND m.import_deleted=0'
    with closing(storage.connect()) as c:
        entries=c.execute(f'SELECT {column} name,COUNT(*) records,SUM(u138+u128+u137) readings,SUM(uprint) copies,SUM(uop) ops,'+
                          ','.join(f'SUM({v}) "{k}"' for k,v in COLS.items())+' FROM record_metrics m WHERE '+condition+
                          f' GROUP BY {column} ORDER BY readings DESC,{column}',args).fetchall()
    return [{LABELS[column]:r['name'],'Registros':r['records'],'Leituras faturáveis':r['readings'],
             'Comunicados':r['copies'],'Apontamentos':r['ops'],'total_cents':sum(r[k]*prices[k] for k in COLS)} for r in entries]

def record_page(month,start=None,end=None,category='Todos',mode='Todos',offset=0,limit=100):
    if not 1<=limit<=500 or offset<0:raise ValueError('Paginação inválida.')
    condition,args=where(month,start,end)
    if category!='Todos':condition+=' AND m.'+COLS[category]+'>0'
    if mode=='Com erros':condition+=' AND m.errors>0'
    elif mode=='Com avisos':condition+=' AND m.alerts>0'
    elif mode=='Excluídos':condition+=' AND (m.excluded<>0 OR m.import_deleted<>0)'
    elif mode=='Chaves repetidas':
        dup,dupargs=duplicates(month);condition+=' AND m.excluded=0 AND m.import_deleted=0 AND m.business_key IN ('+dup+')';args.extend(dupargs)
    with closing(storage.connect()) as c:
        count=c.execute('SELECT COUNT(*) FROM record_metrics m WHERE '+condition,args).fetchone()[0]
        # Select only small IDs before joining large JSON payloads, including late pages.
        selected=c.execute('SELECT r.*,i.name,i.sheet FROM records r JOIN imports i ON i.id=r.import_id WHERE r.id IN (SELECT m.id FROM record_metrics m WHERE '+condition+' ORDER BY m.id LIMIT ? OFFSET ?) AND r.month=? ORDER BY r.id',
                           [*args,limit,offset,month]).fetchall()
    return count,[{**dict(r),'record_excluded':r['excluded'],'excluded':int(bool(r['excluded'] or r['import_deleted'])),
                   'raw':json.loads(r['raw']),'result':json.loads(r['result'])} for r in selected]

def record(month,row_id):
    with closing(storage.connect()) as c:
        r=c.execute('SELECT r.*,i.name,i.sheet FROM records r JOIN imports i ON i.id=r.import_id WHERE r.month=? AND r.id=?',(month,row_id)).fetchone()
    return None if r is None else {**dict(r),'record_excluded':r['excluded'],'excluded':int(bool(r['excluded'] or r['import_deleted'])),
                                 'raw':json.loads(r['raw']),'result':json.loads(r['result'])}
