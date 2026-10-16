"""Recálculo direto do Excel: não abre banco de produção nem lê a tabela dinâmica."""
import argparse,collections,datetime,hashlib,json,sqlite3,tempfile,unicodedata
from pathlib import Path
import openpyxl
from inspection_catalog import MAPPING,EXCLUDED

def normalize(v):return ' '.join(''.join(c for c in unicodedata.normalize('NFKD',str(v or '')) if not unicodedata.combining(c)).upper().split())
def initial_catalog():
    rules=[{'tss':normalize(tss),'cause':'','form':'','code':code,'decision':'Cobrar'} for code,items in MAPPING.items() for tss in items]
    rules.extend({'tss':normalize(tss),'cause':'','form':'','code':None,'decision':'Excluir'} for tss in EXCLUDED)
    return {'prices':{'200014104':{'cents':1200,'active':1},'200014105':{'cents':2250,'active':1},'200014106':{'cents':2250,'active':1}},'rules':rules,'reviews':{},'scope':'Catálogo inicial confirmado em 15/10/2026, para setembro/2026 em diante.'}

def run(files,month,output,catalog=None,references=None,progress=print):
    datetime.date.fromisoformat(month+'-01');output=Path(output);output.mkdir(parents=True,exist_ok=True)
    if any((output/n).exists() for n in ['calculo_vistorias.json','conferencia_vistorias.xlsx']):raise ValueError('Saída já existe; escolha outra pasta para preservar os resultados anteriores.')
    if catalog is None and month<'2026-09':raise ValueError('Forneça catálogo com vigência comprovada para competência anterior a setembro/2026.')
    config=catalog or initial_catalog()
    if config.get('month',month)!=month:raise ValueError('O catálogo exportado pertence a outra competência.')
    result={'month':month,'files':[],'quantities':{},'cents':{},'reasons':{},'processed':0,'scope':config.get('scope','Configuração exportada do sistema')};byrules=collections.defaultdict(list)
    for rule in config['rules']:byrules[normalize(rule['tss'])].append(rule)
    w=openpyxl.Workbook(write_only=True);sheet=w.create_sheet('Registros 1');sheet.append(['Arquivo','Aba','Linha','OS','Execução','Município','TSS','Código','Motivo','Valor centavos'])
    with tempfile.TemporaryDirectory(prefix='vistorias-independente-') as temp:
        with sqlite3.connect(Path(temp)/'scratch.sqlite3') as c:
            c.execute('CREATE TABLE source(id INTEGER PRIMARY KEY,file TEXT,line INTEGER,os TEXT,contract TEXT,day TEXT,city TEXT,tss TEXT,cause TEXT,form TEXT,closed INTEGER,raw_hash TEXT)')
            for file in map(Path,files):
                before=hashlib.sha256(file.read_bytes()).hexdigest();book=openpyxl.load_workbook(file,read_only=True,data_only=True)
                try:
                    s=book['Número OS'];rows=s.iter_rows(values_only=True);headers=next(rows)
                    required=['Número OS','Status da OS','Status da Operação','Data Fim Execução','TSS']
                    if not all(h in headers for h in required):raise ValueError('Cabeçalhos obrigatórios ausentes.')
                    batch=[];n=0
                    for line,values in enumerate(rows,2):
                        if not any(v is not None and str(v).strip() for v in values):continue
                        r=dict(zip(headers,values));value=r.get('Data Fim Execução')
                        try:dt=value if isinstance(value,datetime.datetime) else datetime.datetime.strptime(str(value).strip(),'%d/%m/%Y %H:%M');day=dt.date().isoformat()
                        except (ValueError,TypeError):day=None
                        raw_hash=hashlib.sha256(json.dumps(r,ensure_ascii=False,default=str).encode()).hexdigest()
                        batch.append((file.name,line,str(r.get('Número OS') or ''),normalize(r.get('Contrato')),day,str(r.get('Município') or 'Não informado'),normalize(r.get('TSS')),normalize(r.get('Causa Resultado')),normalize(r.get('Formulário de Baixa')),int(all(normalize(r.get(k))=='FECHADA' for k in ('Status da OS','Status da Operação'))),raw_hash));n+=1
                        if len(batch)>=2000:c.executemany('INSERT INTO source(file,line,os,contract,day,city,tss,cause,form,closed,raw_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?)',batch);batch=[];progress(f'{file.name}: {n} linhas lidas')
                    if batch:c.executemany('INSERT INTO source(file,line,os,contract,day,city,tss,cause,form,closed,raw_hash) VALUES(?,?,?,?,?,?,?,?,?,?,?)',batch)
                finally:book.close()
                if hashlib.sha256(file.read_bytes()).hexdigest()!=before:raise ValueError('Arquivo mudou durante a leitura.')
                result['files'].append({'name':file.name,'sha256':before,'rows':n})
            c.execute('CREATE INDEX source_os ON source(contract,os,day)');c.row_factory=sqlite3.Row
            c.execute('CREATE TEMP TABLE repeated AS SELECT contract,os FROM source WHERE substr(day,1,7)=? AND os<>\'\' GROUP BY contract,os HAVING COUNT(*)>1',(month,));c.execute('CREATE INDEX repeated_key ON repeated(contract,os)')
            query='SELECT s.*,EXISTS(SELECT 1 FROM repeated d WHERE d.contract=s.contract AND d.os=s.os) repeated FROM source s WHERE substr(day,1,7)=? OR (day IS NULL AND closed=1) ORDER BY id'
            quantities=collections.Counter();amounts=collections.Counter();reasons=collections.Counter();tsstotals=collections.Counter();linecount=0
            for r in c.execute(query,(month,)):
                candidates=[rule for rule in byrules[r['tss']] if (not rule.get('cause') or normalize(rule['cause'])==r['cause']) and (not rule.get('form') or normalize(rule['form'])==r['form'])]
                if candidates:
                    score=lambda rule:bool(rule.get('cause'))+bool(rule.get('form'))
                    best=max(score(rule) for rule in candidates);candidates=[rule for rule in candidates if score(rule)==best]
                review=config.get('reviews',{}).get(r['raw_hash']);rule=review or (candidates[0] if len(candidates)==1 else None);code=rule.get('code') if rule else None
                if not r['closed']:reason='Não concluída'
                elif not r['day']:reason='Pendente: data de execução'
                elif rule and rule['decision']=='Excluir':reason='Excluído por classificação confirmada'
                elif not review and r['repeated']:reason='Pendente: OS repetida'
                elif not review and r['tss']=='VISTORIA LIGACAO INATIVA SEM DEBITO':reason='Pendente: ligação inativa'
                elif not review and len(candidates)>1:reason='Pendente: regras ambíguas'
                elif rule and rule['decision']=='Pendente':reason='Pendente: classificação definida pelo usuário'
                elif not r['os']:reason='Pendente: OS ausente'
                elif not rule:reason='Pendente: serviço não mapeado'
                elif code not in config['prices'] or not config['prices'][code]['active']:reason='Pendente: preço ausente ou serviço inativo'
                else:reason='Faturável'
                override=config.get('tss_prices',{}).get(r['tss'],{}).get('cents')
                cents=(override if override is not None else config['prices'][code]['cents']) if reason=='Faturável' else 0
                if reason=='Faturável':quantities[code]+=1;amounts[code]+=cents
                reasons[reason]+=1;tsstotals[(r['tss'],code,reason)]+=1
                if linecount and linecount%1048575==0:sheet=w.create_sheet('Registros '+str(linecount//1048575+1));sheet.append(['Arquivo','Aba','Linha','OS','Execução','Município','TSS','Código','Motivo','Valor centavos'])
                # Texto literal evita interpretar conteúdo da origem como fórmulas no relatório.
                from openpyxl.cell import WriteOnlyCell
                values=[r['file'],'Número OS',r['line'],r['os'],r['day'],r['city'],r['tss'],code,reason,cents];cells=[]
                for value in values:
                    if isinstance(value,str):cell=WriteOnlyCell(sheet,value=value);cell.data_type='s';cells.append(cell)
                    else:cells.append(value)
                sheet.append(cells);linecount+=1
                if linecount%2000==0:progress(f'{linecount} registros recalculados')
            result.update(quantities=dict(quantities),cents=dict(amounts),total_cents=sum(amounts.values()),reasons=dict(reasons),processed=linecount,catalog_sha256=hashlib.sha256(json.dumps(config,sort_keys=True,ensure_ascii=False).encode()).hexdigest())
            # Somente depois da apuração, referências opcionais entram na comparação.
            result['comparison']={code:{'calculated':quantities[code],'reference':ref,'difference':quantities[code]-ref} for code,ref in (references or {}).items()}
            s=w.create_sheet('Comparação');s.append(['Código','Quantidade calculada','Referência informada','Diferença'])
            for code,r in result['comparison'].items():s.append([code,r['calculated'],r['reference'],r['difference']])
            s=w.create_sheet('Resumo');s.append(['Código','Quantidade','Valor centavos'])
            for code in config['prices']:
                if code!='geo':s.append([code,quantities[code],amounts[code]])
            s=w.create_sheet('Motivos');s.append(['Motivo','Quantidade'])
            for key,n in reasons.items():s.append([key,n])
            s=w.create_sheet('TSS');s.append(['TSS','Código','Motivo','Quantidade'])
            for (tss,code,reason),n in sorted(tsstotals.items(),key=lambda x:str(x[0])):s.append([tss,code,reason,n])
    (output/'calculo_vistorias.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));w.save(output/'conferencia_vistorias.xlsx');progress('Concluído. Nenhum banco de produção foi aberto.');return result
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('files',nargs='+',type=Path);p.add_argument('--mes',required=True);p.add_argument('--saida',type=Path,required=True);p.add_argument('--catalogo',type=Path);p.add_argument('--referencias',type=Path);a=p.parse_args()
    run(a.files,a.mes,a.saida,json.loads(a.catalogo.read_text()) if a.catalogo else None,json.loads(a.referencias.read_text()) if a.referencias else None)
