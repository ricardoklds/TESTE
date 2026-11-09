"""Consultas SQL limitadas e agregadas sobre resultados já calculados."""
import json
from contextlib import closing, nullcontext
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

def overview(month,start=None,end=None,*,connection=None):
    condition,args=where(month,start,end)
    eligible='m.excluded=0 AND m.import_deleted=0'+(' AND m.errors=0' if start is not None else '')
    with (nullcontext(connection) if connection is not None else closing(storage.connect())) as c:
        combined=c.execute('''SELECT COUNT(*) total_records,COUNT(DISTINCT import_id) import_count,
            COALESCE(SUM(excluded<>0 OR import_deleted<>0),0) excluded_count,
            COALESCE(SUM(excluded=0 AND import_deleted=0),0) active_count,
            COALESCE(SUM(excluded=0 AND import_deleted=0 AND errors=0),0) valid_count,
            COALESCE(SUM(excluded=0 AND import_deleted=0 AND errors>0),0) errors,
            '''+','.join(f'COALESCE(SUM(CASE WHEN {eligible} THEN {v} ELSE 0 END),0) AS "{k}"' for k,v in COLS.items())+
            ' FROM record_metrics m WHERE '+condition,args).fetchone()
        units={k:combined[k] for k in COLS}
        stats={k:combined[k] for k in combined.keys() if k not in COLS}
        dup,dup_args=duplicates(month)
        extra=' AND day BETWEEN ? AND ?' if start is not None else ''
        conflicts=c.execute('SELECT COUNT(DISTINCT business_key) FROM record_metrics WHERE month=? AND excluded=0 AND import_deleted=0 AND business_key IN ('+dup+')'+extra,
                            [month,*dup_args,*([start,end] if start is not None else [])]).fetchone()[0]
        undated=c.execute('SELECT COUNT(*) FROM record_metrics WHERE month=? AND day IS NULL',(month,)).fetchone()[0]
    return {**dict(stats),'units':dict(units),'conflicts':conflicts,'undated':undated}

def import_listing(month,prices):
    """Uma agregação para todos os arquivos; impacto de exclusão só na confirmação."""
    import holidays
    with closing(storage.connect()) as c:
        charge_sql,args=holidays.charges_query(c,month)
        holiday_counts={r['import_id']:r['n'] for r in c.execute(
            'SELECT m.import_id,COUNT(*) n FROM ('+charge_sql+') h JOIN record_metrics m ON m.id=h.id GROUP BY m.import_id',args)}
        sql='''SELECT i.*,COUNT(m.id) record_count,
            COALESCE(SUM(m.excluded=0 AND m.import_deleted=0),0) active_count,'''+','.join(
            f'COALESCE(SUM(CASE WHEN m.excluded=0 AND m.import_deleted=0 THEN m.{v} ELSE 0 END),0) "{k}"'
            for k,v in COLS.items())+''' FROM imports i LEFT JOIN record_metrics m ON m.import_id=i.id
            WHERE i.month=? GROUP BY i.id ORDER BY i.id'''
        return [{**dict(r),'total_cents':sum(r[k]*prices[k] for k in COLS)+105*holiday_counts.get(r['id'],0)}
                for r in c.execute(sql,(month,))]

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
