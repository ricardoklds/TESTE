from datetime import date
from decimal import Decimal
import hashlib
import pandas as pd
import streamlit as st
import core
import storage
import periods
import queries
import cached_queries as cached
import excel_io
import fast_reports
import holidays
import holiday_review
import localities
from exports import money, productivity, excel_report, pdf_report

st.set_page_config(page_title='Gestão de Medição | Fechamento',page_icon='💧',layout='wide')
st.markdown('''<style>
.block-container{padding-top:2rem;max-width:1450px} h1{font-weight:750;letter-spacing:-1px}
[data-testid="stSidebar"]{background:#163a60} [data-testid="stSidebar"] *{color:#f7fafc}
[data-testid="stMetric"]{background:white;border:1px solid #dce5ee;border-radius:12px;padding:18px}
.stButton button{border-radius:8px} [data-testid="stSidebar"] input{color:#163a60}
</style>''',unsafe_allow_html=True)

@st.cache_data(show_spinner=False,max_entries=8)
def parsed_file(content):
    return excel_io.inspect(content)

with st.sidebar:
    st.title('💧 Medição')
    st.caption('GESTÃO DO CONTRATO · LEITURAS')
    page=st.radio('Navegação',['Painel inicial','Importar planilhas','Fechamento mensal','Produtividade','Relatórios','Configurações'],label_visibility='collapsed')
    st.divider()
    reference=st.date_input('Mês de referência',value=date(2026,10,1),format='DD/MM/YYYY')
    month=reference.strftime('%Y-%m')
    st.caption('O dia selecionado não afeta o fechamento.')
    st.caption('Dados locais · Originais preservados')

info=storage.month_info(month);prices=info['prices']
revision=queries.revision();cache_path=str(storage.DATA.resolve())
monthly=cached.overview(cache_path,revision,month)
monthly_summary=queries.summary(monthly,prices)
monthly_total=sum(r['total_cents'] for r in monthly_summary)
errors=monthly['errors'];conflicts=monthly['conflicts']
summary=monthly_summary;total=monthly_total;stats=monthly
st.caption(f"CONTRATO SABESP · {month} · {'FECHADO' if info['closed'] else 'EM CONFERÊNCIA'}")
st.title(page)
period_pages=('Painel inicial','Fechamento mensal','Produtividade')
start_arg=end_arg=None
mappings=periods.import_mappings(storage.imports(month)) if page=='Fechamento mensal' else {}
if page in period_pages:
    first,last=periods.month_bounds(month)
    mode=st.radio('Período de visualização',['Mês completo','Dia específico','Intervalo personalizado'],horizontal=True,key='period_mode')
    start,end=first,last
    if mode=='Dia específico':
        start=end=st.date_input('Dia da leitura',value=first,min_value=first,max_value=last,format='DD/MM/YYYY',key='period_day_'+month)
    elif mode=='Intervalo personalizado':
        c1,c2=st.columns(2)
        start=c1.date_input('Data inicial',value=first,min_value=first,max_value=last,format='DD/MM/YYYY',key='period_start_'+month)
        end=c2.date_input('Data final',value=last,min_value=first,max_value=last,format='DD/MM/YYYY',key='period_end_'+month)
    try:
        start_arg,end_arg=periods.query_bounds(month,mode,start,end)
    except ValueError as e:
        st.error(str(e));start_arg=end_arg='9999-12-31'
    stats=cached.overview(cache_path,revision,month,start_arg,end_arg)
    summary=queries.summary(stats,prices);total=sum(r['total_cents'] for r in summary)
    if mode=='Mês completo':st.caption('Mês completo: acumulado do mês de referência, incluindo registros sem data conforme as regras existentes.')
    else:st.caption(f'Período inclusivo: {start:%d/%m/%Y} a {end:%d/%m/%Y} · coluna Data da Leitura Atual · dentro de {month}.')
    st.info(f'Acumulado mensal preservado: {money(monthly_total)} · {monthly["total_records"]} registros importados. O filtro não altera o fechamento nem os relatórios mensais.')
    if errors or conflicts:st.warning(f'Pendências no mês inteiro: {errors} registros com erros e {conflicts} chaves repetidas. A identificação mensal permanece ativa independentemente do filtro.')
    if page!='Painel inicial' and monthly['undated']:st.caption(f'{monthly["undated"]} registros sem data válida na projeção: preservados no acumulado conforme as regras originais; fora dos filtros por dia e intervalo.')
    if page=='Painel inicial' and monthly['undated']:st.caption('Registros sem data são preservados no acumulado e permanecem disponíveis na auditoria técnica.')
    if not stats['valid_count']:st.info('Nenhum registro válido no período selecionado.')

def metrics():
    cols=st.columns(4)
    cols[0].metric('Faturamento do período' if page in period_pages else 'Faturamento mensal',money(total))
    cols[1].metric('Leituras faturáveis',f"{sum(r['Quantidade'] for r in summary if r['key'] in ('138','128','137')):,}".replace(',','.'))
    cols[2].metric('Registros válidos do período' if page in period_pages else 'Registros ativos',f'{stats["valid_count"] if page in period_pages else stats["active_count"]:,}'.replace(',','.'))
    cols[3].metric('Pendências no período' if page in period_pages else 'Pendências',stats['errors']+stats['conflicts']+stats.get('holiday_pending',0))

def summary_frame():
    return pd.DataFrame([{'Código':r['Código'],'Serviço':r['Categoria'],'Quantidade':r['Quantidade'],'Valor unitário':money(r['unit_cents']),'Total':money(r['total_cents'])} for r in summary])

def record_frame(selected):
    return pd.DataFrame([{'ID':r['id'],'Arquivo':r['name'],'Aba':r['sheet'],'Linha original':r['line'],'Data da leitura':str(r['raw'].get(mappings.get(r['import_id'], {}).get('date')) or ''),'Funcionário':r['result']['employee'],'ATC':r['result']['city'],'Excluído':bool(r['excluded']),'Motivo':r['reason'],'Erros':'; '.join(r['result']['errors']),'Avisos':'; '.join(r['result']['alerts']),**{core.CATEGORIES[k][1]:v for k,v in r['result']['units'].items()}} for r in selected])

if page=='Painel inicial':
    import managerial_ui
    managerial_ui.render(cache_path,revision,month,prices,start_arg,end_arg,dashboard=True)

elif page=='Importar planilhas':
    st.write('Importe uma aba por vez. O arquivo original é arquivado integralmente e identificado por SHA-256.')
    if info['closed']:st.warning('Este mês está fechado. Os originais e o histórico continuam disponíveis; reabra para importar, excluir ou restaurar.')
    if message:=st.session_state.pop('import_message',None):st.success(message)
    uploaded=st.file_uploader('Planilha de leitura (.xlsx)',type=['xlsx'],disabled=bool(info['closed']))
    if uploaded:
        content=uploaded.getvalue()
        try:parsed=parsed_file(content)
        except Exception as e:st.error(f'Não foi possível ler a planilha: {e}');st.stop()
        selected=st.selectbox('Aba',[p['sheet'] for p in parsed]);p=next(p for p in parsed if p['sheet']==selected)
        st.success(f"Prévia de até {len(p['records']):,} linhas; contagem completa ao importar · {len(p['headers'])} colunas · cabeçalho na linha {p['header_row']}".replace(',','.'))
        st.caption('SHA-256: '+hashlib.sha256(content).hexdigest())
        with st.expander('Todas as colunas identificadas',expanded=False):st.dataframe(pd.DataFrame({'Coluna':p['headers']}),hide_index=True)
        st.subheader('Correspondência das colunas')
        mapping={};cols=st.columns(3);options=['Não disponível',*p['headers']]
        for n,(key,label) in enumerate(core.FIELDS.items()):
            default=p['mapping'][key];index=options.index(default) if default else 0
            with cols[n%3]:
                chosen=st.selectbox(label+(' *' if key in core.REQUIRED else ''),options,index=index,key=f'map_{hashlib.sha256(content).hexdigest()}_{selected}_{key}')
                mapping[key]=None if chosen=='Não disponível' else chosen
        st.caption('* Obrigatório. Os dados não são alterados pelo mapeamento.')
        st.dataframe(pd.DataFrame([r['raw'] for r in p['records'][:15]]).astype(str),hide_index=True)
        confirmed=st.checkbox(f'Confirmo o mapeamento e o mês {month}. Incluir sem data, releituras e adicionais em faturas retidas, conforme regras confirmadas.')
        if st.button('Processar e importar',type='primary',disabled=not confirmed or bool(info['closed'])):
            try:
                with st.status('Preservando o original e processando em lotes…') as status:
                    progress=st.empty()
                    def report_progress(processed,inserted,duplicates):
                        progress.write(f'Linhas processadas: {processed:,} · Inseridas: {inserted:,} · Duplicatas ignoradas: {duplicates:,}. Aguardando conclusão da transação.')
                    added,skipped=storage.import_sheet(content,uploaded.name,{**p,'records':excel_io.iter_records(content,p)},mapping,month,on_progress=report_progress)
                    status.update(label='Importação confirmada no banco',state='complete')
                st.session_state['import_message']=f'Importação concluída: {added} registros inseridos; {skipped} duplicatas idênticas ignoradas.'
                st.session_state.pop('exports',None)
                st.rerun()
            except Exception as e:st.error(str(e))
    with st.expander('Arquivos importados e originais',expanded=True):
        st.caption('Operações por aba/importação do mês selecionado. Excluir não apaga o original. Valores usam os preços atuais deste mês.')
        for entry in cached.import_listing(cache_path,revision,month,prices):
            preview=entry
            st.write(f"**{entry['name']}** · {entry['sheet']} · {'Excluído' if entry['deleted'] else 'Ativo'}")
            st.caption(f"Importado em UTC: {entry['created_at']} · Mês: {month} · Registros vinculados: {preview['record_count']} · No fechamento: {preview['active_count']} · Faturamento: {money(preview['total_cents'])}")
            left,right=st.columns(2)
            if left.button('Preparar download original',key=f"prepare_original_{entry['id']}"):
                st.session_state['prepared_original']=entry['sha']
                st.session_state['original_bytes']=(storage.DATA/'originais'/(entry['sha']+'.xlsx')).read_bytes()
            if st.session_state.get('prepared_original')==entry['sha'] and 'original_bytes' in st.session_state:
                left.download_button('Baixar original intacto',st.session_state['original_bytes'],file_name=entry['name'],key=f"original_{entry['id']}")
            deleted=not bool(entry['deleted'])
            if right.button('Excluir importação' if deleted else 'Restaurar importação',key=f"action_import_{entry['id']}",disabled=bool(info['closed'])):
                preview=cached.import_preview(cache_path,revision,month,entry['id'])
                st.session_state['import_action']={'month':month,'id':entry['id'],'deleted':deleted,'preview':preview}
            st.divider()
        pending=st.session_state.get('import_action')
        if pending and pending['month']==month:
            preview=pending['preview'];action='exclusão' if pending['deleted'] else 'restauração'
            st.warning(f"Confirmar {action}: {preview['name']} · Aba: {preview['sheet']} · Mês: {month}. "
                       f"{preview['record_count']} registros vinculados; {preview['potential_count']} registros sairão/voltarão ao fechamento. "
                       f"Impacto estimado: {'−' if pending['deleted'] else '+'}{money(preview['potential_cents'])}. Outros arquivos e meses serão preservados.")
            with st.form('confirm_import_'+str(pending['id'])+'_'+preview['version']):
                reason=st.text_input('Justificativa da exclusão ou restauração')
                confirmed=st.checkbox(f'Confirmo explicitamente a {action} desta importação.')
                submit=st.form_submit_button('Confirmar operação',disabled=bool(info['closed']))
            if submit:
                if not confirmed:st.error('Marque a confirmação explícita antes de prosseguir.')
                else:
                    try:
                        storage.set_import_deleted(month,pending['id'],pending['deleted'],reason,preview['version'])
                        st.session_state.pop('exports',None);st.session_state.pop('import_action',None)
                        st.session_state['import_message']='Importação excluída do fechamento.' if pending['deleted'] else 'Importação restaurada sem duplicidades.'
                        st.rerun()
                    except ValueError as e:st.error(str(e))
            if st.button('Cancelar operação'):
                st.session_state.pop('import_action',None);st.rerun()
        with st.expander('Histórico de exclusões e restaurações'):
            st.dataframe(pd.DataFrame([r for r in storage.audit(month) if r['action'] in ('Excluir importação','Restaurar importação')]),hide_index=True)
        st.subheader('Comprovação de execução no Brasil')
        st.caption('Use apenas quando o arquivo tiver comprovação documental brasileira e não for possível resolver cada município. A comprovação habilita somente feriados nacionais; não preenche município ou UF. Não confirme apenas por haver um prefixo ATC desconhecido.')
        entries=storage.imports(month)
        if entries:
            with st.form('brazil_execution_proof'):
                selected_id=st.selectbox('Importação com execução comprovada',[e['id'] for e in entries],format_func=lambda x:next(e['name']+' · '+e['sheet'] for e in entries if e['id']==x))
                evidence=st.text_input('Referência ou descrição da evidência documental')
                confirmed_brazil=st.checkbox('Conferi a documentação e confirmo que esta execução ocorreu no Brasil')
                if st.form_submit_button('Registrar comprovação brasileira',disabled=bool(info['closed'])):
                    if not confirmed_brazil:st.error('É necessária confirmação explícita baseada em documentação.')
                    else:
                        try:localities.prove_brazil(selected_id,evidence);st.session_state.pop('exports',None);st.rerun()
                        except ValueError as e:st.error(str(e))

elif page=='Fechamento mensal':
    metrics();st.dataframe(summary_frame(),hide_index=True,width='stretch')
    if errors or conflicts:st.error(f'No mês completo: {errors} registros com erros e {conflicts} chaves repetidas. O filtro não oculta pendências para autorizar fechamento; resolva antes de fechar.')
    with st.expander('Conferência do adicional de feriado',expanded=True):
        st.caption('R$ 1,05 por fornecimento/data/execução. Nacional exige Brasil comprovado; estadual exige UF segura; municipal exige município e UF seguros. Domingos não são cobrados automaticamente.')
        st.write(f"Elegíveis cobrados: {stats['holiday_quantity']} · Pendências: {stats['holiday_pending']}")
        options=cached.holiday_options(cache_path,revision,month,start_arg,end_arg)
        hc=st.columns(3)
        town_filter=hc[0].selectbox('Município/UF do adicional',[None,*options['municipality']],format_func=lambda x:'Todos' if x is None else ('Não confirmado' if x=='/' else x))
        group_filter=hc[1].selectbox('Grupo do adicional',[None,*options['group']],format_func=lambda x:'Todos' if x is None else x)
        employee_filter=hc[2].selectbox('Funcionário do adicional',[None,*options['employee']],format_func=lambda x:'Todos' if x is None else x)
        situation_filter=st.selectbox('Situação',holiday_review.SITUATIONS)
        n,first_h=cached.holiday_page(cache_path,revision,month,start_arg,end_arg,0,100,town_filter,group_filter,employee_filter,situation_filter)
        number=st.number_input('Página de feriados',min_value=1,max_value=max(1,(n+99)//100),value=1,step=1,key=f'holiday_page_{month}_{revision}_{start_arg}_{end_arg}_{town_filter}_{group_filter}_{employee_filter}_{situation_filter}')
        hrows=first_h if number==1 else cached.holiday_page(cache_path,revision,month,start_arg,end_arg,(number-1)*100,100,town_filter,group_filter,employee_filter,situation_filter)[1]
        st.caption(f'{n} registros na conferência do adicional.')
        columns=[k for k in holiday_review.FIELDS if k!='reason']+['status','Cobrado','Valor (R$)']
        st.dataframe(pd.DataFrame(hrows,columns=columns).rename(columns={**holiday_review.FIELDS,'status':'Motivo / situação'}),hide_index=True,width='stretch')
        reasons=cached.holiday_pending_summary(cache_path,revision,month,start_arg,end_arg,town_filter,group_filter,employee_filter)
        st.write(f"Pendências nos filtros de período/localidade/grupo/funcionário: {sum(r['Quantidade'] for r in reasons)}")
        st.dataframe(pd.DataFrame(reasons,columns=['Motivo','Quantidade']),hide_index=True,width='stretch')
        st.caption('Não cobrados inclui pendências, duplicatas e leituras de outro município sem adicional. O resumo e o Excel contêm somente pendências, respeitando os filtros de período, município, grupo e funcionário. A conferência pode corrigir a classificação municipal de meses fechados, preservando os dados gravados e as cobranças congeladas.')
        export_key=(revision,month,start_arg,end_arg,town_filter,group_filter,employee_filter)
        job=st.session_state.get('holiday_pending_job')
        if st.button('Exportar pendências para Excel',disabled=not reasons or bool(job and not job[1].done())):
            st.session_state['holiday_pending_job']=(export_key,fast_reports.EXECUTOR.submit(holiday_review.pending_excel,str(storage.DATA/'contrato.sqlite3'),*export_key))
        @st.fragment(run_every='2s')
        def pending_export_status():
            job=st.session_state.get('holiday_pending_job')
            if not job:return
            if not job[1].done():st.info('Gerando Excel das pendências em segundo plano…');return
            try:
                path=job[1].result()
                if job[0]!=export_key or queries.revision()!=revision:
                    st.warning('Os dados ou filtros mudaram. Exporte as pendências novamente.');return
                if st.button('Preparar download das pendências'):
                    st.session_state['prepared_holiday_pending']=str(path)
                if st.session_state.get('prepared_holiday_pending')==str(path):
                    with path.open('rb') as file:st.download_button('Baixar pendências em Excel',file,file_name=path.name,mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            except Exception as e:st.error(f'Falha na exportação das pendências: {e}')
        pending_export_status()
    st.subheader('Conferência dos registros')
    category=st.selectbox('Categoria',['Todos',*[core.CATEGORIES[k][1] for k in core.CATEGORIES]])
    mode=st.selectbox('Exibir',['Todos','Com erros','Com avisos','Chaves repetidas','Excluídos'])
    category_key='Todos' if category=='Todos' else next(k for k,v in core.CATEGORIES.items() if v[1]==category)
    def show_records(prefix,begin,finish,category_key='Todos',mode='Todos'):
        size=st.selectbox('Registros por página',[100,250,500],key=prefix+'_size')
        count,first_page=cached.record_page(cache_path,revision,month,begin,finish,category_key,mode,0,size)
        pages=max(1,(count+size-1)//size)
        page_number=st.number_input('Página',min_value=1,max_value=pages,value=1,step=1,key=f'{prefix}_{month}_{begin}_{finish}_{category_key}_{mode}_{size}_{revision}')
        selected=first_page if page_number==1 else cached.record_page(cache_path,revision,month,begin,finish,category_key,mode,(page_number-1)*size,size)[1]
        st.caption(f'{count} registros encontrados · página {page_number} de {pages}.')
        st.dataframe(record_frame(selected),hide_index=True,width='stretch')
    show_records('period_records',start_arg,end_arg,category_key,mode)
    if st.checkbox('Mostrar histórico mensal completo (paginado)'):
        show_records('monthly_records',None,None)
    with st.expander('Inspecionar dados originais / registrar decisão'):
        row_id=st.number_input('ID do registro',min_value=1,step=1)
        row=queries.record(month,row_id)
        if row:
            st.dataframe(pd.DataFrame({'Coluna':list(row['raw']),'Valor original':[str(v) if v is not None else '' for v in row['raw'].values()]}),hide_index=True)
            reason=st.text_input('Justificativa da decisão')
            if row['import_deleted']:st.info('Registro de importação excluída. Restaure o arquivo na tela Importar planilhas.')
            if st.button('Reincluir registro' if row['excluded'] else 'Excluir do faturamento',disabled=bool(info['closed'] or row['import_deleted'])):
                try:storage.exclude(month,row_id,reason,not bool(row['excluded']));st.session_state.pop('exports',None);st.rerun()
                except ValueError as e:st.error(str(e))
    if info['closed']:
        st.success(f"Fechamento registrado em UTC: {info['closed_at']}. Preços e importações bloqueados.")
        reason=st.text_input('Motivo de reabertura')
        if st.button('Reabrir mês'):
            try:storage.close_month(month,False,reason);st.session_state.pop('exports',None);st.rerun()
            except ValueError as e:st.error(str(e))
    else:
        st.caption(f'Confirmar fecha o mês INTEIRO ({money(monthly_total)}), independentemente do filtro atual.')
        confirmed=st.checkbox('Conferi os registros do mês inteiro e aprovo o fechamento mensal.')
        if st.button('Confirmar fechamento',type='primary',disabled=not confirmed or not monthly["active_count"] or bool(errors or conflicts)):
            try:storage.close_month(month);st.session_state.pop('exports',None);st.rerun()
            except ValueError as e:st.error(str(e))
    with st.expander('Histórico de alterações'):st.dataframe(pd.DataFrame(storage.audit(month)),hide_index=True)

elif page=='Produtividade':
    st.write('Leituras faturáveis e adicionais separados. Registros excluídos não entram na produtividade.')
    metrics()
    dimension=st.radio('Agrupar por',['Funcionário','Unidade / cidade (ATC)','Grupo'],horizontal=True)
    by={'Funcionário':'employee','Unidade / cidade (ATC)':'city','Grupo':'group'}[dimension];items=cached.productivity(cache_path,revision,month,prices,by,start_arg,end_arg)
    if not items:st.info('Não há produtividade válida no período selecionado.');st.stop()
    frame=pd.DataFrame(items);label=frame.columns[0]
    goals=storage.settings().get('goals',{}).get(month,{})
    frame['Meta mensal de leituras']=[goals.get(by+'|'+str(v)) for v in frame[label]]
    frame['Atingimento da meta mensal no período (%)']=[round(100*r['Leituras faturáveis']/g,1) if g else None for r,g in zip(items,frame['Meta mensal de leituras'])]
    frame['Faturamento']=frame['total_cents'].map(money)
    st.dataframe(frame.drop(columns=['total_cents']),hide_index=True,width='stretch')
    st.subheader('Leituras faturáveis · 15 maiores volumes')
    st.bar_chart(frame.head(15).set_index(label)['Leituras faturáveis'],color='#147D92')
    st.caption('Meta em branco significa não definida. A meta continua mensal: o atingimento compara as leituras do período com a meta mensal, sem rateio ou meta diária presumida.')
    with st.form('goal'):
        who=st.selectbox('Definir meta para',frame[label].tolist());target=st.number_input('Meta mensal de leituras faturáveis',min_value=0,step=1)
        if st.form_submit_button('Salvar meta'):
            all_goals=storage.settings().get('goals',{});all_goals.setdefault(month,{})
            if target:all_goals[month][by+'|'+who]=target
            else:all_goals[month].pop(by+'|'+who,None)
            storage.save_setting('goals',all_goals);st.rerun()

elif page=='Relatórios':
    st.subheader('Relatórios gerenciais')
    import managerial_ui
    managerial_ui.render(cache_path,revision,month,prices,report_period=True)
    st.divider();st.subheader('Relatórios oficiais do mês — sem filtros gerenciais')
    st.write('Exporte o fechamento, produtividade e rastreabilidade. O Excel inclui todas as colunas importadas; o PDF traz indicadores, tabelas e gráfico.')
    metrics();st.dataframe(summary_frame(),hide_index=True,width='stretch')
    contract=storage.settings().get('contract',{})
    goals=storage.settings().get('goals',{}).get(month,{})
    signature=core.fingerprint({'month':month,'prices':prices,'closed':info['closed'],'revision':revision,'contract':contract,'goals':goals})
    if st.button('Gerar Excel e PDF',type='primary',disabled=not monthly['total_records']):
        with st.spinner('Gerando relatórios agregados…'):
            products={by:cached.productivity(cache_path,revision,month,prices,by) for by in ('employee','city','group')}
            args=(month,summary,products,storage.imports(month),storage.audit(month),contract,info['closed'],goals)
            st.session_state['exports']=(signature,fast_reports.summary_excel(*args),pdf_report(month,[],prices,contract,info['closed'],goals,summary_data=summary,productivity_data=products,record_count=monthly['total_records'],excluded_count=monthly['excluded_count']))
    st.caption('Excel/PDF resumidos: totais, produtividade, metas e histórico. A exportação completa é opcional e pode levar minutos em bases grandes.')
    job=st.session_state.get('detailed_job')
    if st.button('Gerar Excel completo em segundo plano',disabled=not monthly['total_records'] or bool(job and not job[1].done())):
        products={by:cached.productivity(cache_path,revision,month,prices,by) for by in ('employee','city','group')}
        args=(month,summary,products,storage.imports(month),storage.audit(month),contract,info['closed'],goals)
        st.session_state['detailed_job']=(signature,fast_reports.EXECUTOR.submit(fast_reports.detailed_excel,str(storage.DATA/'contrato.sqlite3'),revision,month,prices,args))
    @st.fragment(run_every='2s')
    def detailed_status():
        job=st.session_state.get('detailed_job')
        if not job:return
        if not job[1].done():st.info('Gerando Excel completo em segundo plano. Você pode navegar pelas outras telas.');return
        try:
            path=job[1].result()
            if job[0]!=signature or queries.revision()!=revision:st.warning('O relatório completo pertence a uma versão anterior da base. Gere novamente após alterações.');return
            st.success('Excel completo pronto.')
            if st.button('Preparar download do Excel completo'):
                st.session_state['prepared_details']=str(path)
            if st.session_state.get('prepared_details')==str(path):
                with path.open('rb') as file:st.download_button('Baixar Excel completo',file,file_name=path.name)
        except Exception as e:st.error(f'Falha na exportação completa: {e}')
    detailed_status()
    generated=st.session_state.get('exports')
    if generated and generated[0]==signature:
        c1,c2=st.columns(2)
        c1.download_button('Baixar Excel resumido',generated[1],file_name=f'fechamento-{month}.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        c2.download_button('Baixar PDF',generated[2],file_name=f'fechamento-{month}.pdf',mime='application/pdf')
    if not info['closed']:st.info('Relatórios deste mês são prévias até a confirmação do fechamento.')
    if errors or conflicts:st.warning('Há pendências de conferência. Não use a prévia como faturamento aprovado.')

elif page=='Configurações':
    config=storage.settings();contract=config.get('contract',{})
    with st.form('contract'):
        st.subheader('Identificação do contrato')
        name=st.text_input('Empresa prestadora',value=contract.get('name',''))
        number=st.text_input('Número do contrato',value=contract.get('number',''))
        if st.form_submit_button('Salvar identificação'):storage.save_setting('contract',{'name':name,'number':number});st.success('Identificação salva.')
    with st.form('prices'):
        st.subheader('Valores unitários')
        defaults=config.get('prices',{k:v[2] for k,v in core.CATEGORIES.items()});new={}
        for k,(code,label,_) in core.CATEGORIES.items():
            value=st.number_input(f'{code} · {label} (R$)',min_value=0.0,value=defaults[k]/100,step=.01,format='%.2f',key='price_'+k)
            new[k]=int(Decimal(str(value)).quantize(Decimal('.01'))*100)
        apply=st.checkbox(f'Aplicar também ao mês aberto {month}',disabled=bool(info['closed']))
        if st.form_submit_button('Salvar preços'):
            storage.save_setting('prices',new)
            if apply and monthly["total_records"] and not info['closed']:storage.update_month_prices(month,new)
            st.session_state.pop('exports',None);st.success('Preços salvos. Meses fechados mantêm seus valores.');st.rerun()
    st.subheader('Calendário de Feriados')
    st.caption('Nenhum feriado é presumido. Datas cadastradas são exatas, sem recorrência automática. Meses fechados mantêm o adicional congelado; reabra para aplicar alterações.')
    calendar=holidays.calendar()
    st.dataframe(pd.DataFrame(calendar),hide_index=True,width='stretch')
    chosen=st.selectbox('Cadastrar ou editar feriado',['Novo',*[str(h['id'])+' · '+h['day']+' · '+h['description'] for h in calendar]])
    selected=None if chosen=='Novo' else next(h for h in calendar if h['id']==int(chosen.split(' · ')[0]))
    with st.form('holiday_calendar'):
        hdate=st.date_input('Data do feriado',value=date.fromisoformat(selected['day']) if selected else reference)
        description=st.text_input('Descrição do feriado',value=selected['description'] if selected else '')
        scope=st.selectbox('Abrangência',['Nacional','Estadual','Municipal'],index=['Nacional','Estadual','Municipal'].index(selected['scope']) if selected else 0)
        state=st.text_input('UF do feriado (estadual/municipal)',value=selected['state'] if selected else '')
        town=st.text_input('Município do feriado (municipal)',value=selected['municipality'] if selected else '')
        if st.form_submit_button('Salvar feriado'):
            try:holidays.save(hdate.isoformat(),description,scope,state,town,selected['id'] if selected else None);st.session_state.pop('exports',None);st.rerun()
            except ValueError as e:st.error(str(e))
    if selected:
        remove=st.checkbox('Confirmo excluir este feriado do calendário')
        if st.button('Excluir feriado',disabled=not remove):
            holidays.delete(selected['id']);st.session_state.pop('exports',None);st.rerun()
    st.subheader('Identificação automática de municípios e UFs')
    st.caption('Correspondência exata por nomes/códigos IBGE, sem acentos e prefixo ATC; homônimos não recebem município/UF por suposição. Referência comunitária versionada e procedência em reference_data/PROVENANCE.md. Identificações manuais existentes têm prioridade.')
    with storage.connect() as c:
        automatic=[dict(r) for r in c.execute('SELECT * FROM automatic_localities ORDER BY source')]
    st.dataframe(pd.DataFrame(automatic).rename(columns={'source':'Cidade/ATC original normalizada','municipality':'Município','state':'UF','country':'País','evidence':'Referência'}),hide_index=True)
    st.subheader('Municípios e UFs confirmados manualmente')
    st.caption('Associe a origem da coluna de cidade/ATC ao município real do fornecimento. Não use uma ATC que reúna municípios diferentes; esses registros devem permanecer pendentes até uma importação com coluna municipal segura.')
    with storage.connect() as c:
        bindings=[dict(r) for r in c.execute('SELECT * FROM municipality_bindings ORDER BY source')]
        sources=[r[0] for r in c.execute("SELECT DISTINCT source FROM holiday_identity_records WHERE source<>'' ORDER BY source")]
    st.dataframe(pd.DataFrame(bindings),hide_index=True)
    if sources:
        with st.form('municipality_binding'):
            source=st.selectbox('Origem cidade/ATC na planilha',sources)
            municipality=st.text_input('Município confirmado')
            uf=st.text_input('UF confirmada')
            approved=st.checkbox('Confirmo que esta origem identifica exclusivamente este município e UF')
            if st.form_submit_button('Salvar identificação municipal'):
                if not approved:st.error('É necessária confirmação explícita da localidade.')
                else:
                    try:holidays.bind(source,municipality,uf);st.session_state.pop('exports',None);st.rerun()
                    except ValueError as e:st.error(str(e))
    st.subheader('Regras confirmadas')
    st.markdown('''- R$ 1,38: impressa Sim, retida Não e causa vazia.
- R$ 1,28: impressa Não, retida Não e causa vazia.
- R$ 1,37: retida Não e causa preenchida, independentemente da impressão.
- Impressão: soma de Quantidade comunicados impressos × preço.
- Apontamento: cada CO1 Atual preenchido × preço, inclusive códigos de vistoria.
- Adicionais em todos os registros; registros sem data e releituras incluídos.
- Adicional de feriado 200014097: R$ 1,05, calendário/localidade confirmados, retida Não, causa vazia, sem filtro de impressão e sem domingos.
- Serviços de vistoria e demais itens de contrato não são faturados nesta versão.
- Arquivos idênticos não são reimportados no mesmo mês; linhas idênticas são ignoradas. Chaves fornecimento + data + tarefa repetidas exigem conferência antes de fechar.''')
    st.info('Faça backup de toda a pasta data com o sistema parado: ela contém o banco e os arquivos originais. Esta versão é local; não possui autenticação para exposição pública.')
