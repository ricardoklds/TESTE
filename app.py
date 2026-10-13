from datetime import date
from decimal import Decimal
import hashlib
import pandas as pd
import streamlit as st
import core
import storage
from exports import money, productivity, excel_report, pdf_report

st.set_page_config(page_title='Gestão de Medição | Fechamento',page_icon='💧',layout='wide')
st.markdown('''<style>
.block-container{padding-top:2rem;max-width:1450px} h1{font-weight:750;letter-spacing:-1px}
[data-testid="stSidebar"]{background:#163a60} [data-testid="stSidebar"] *{color:#f7fafc}
[data-testid="stMetric"]{background:white;border:1px solid #dce5ee;border-radius:12px;padding:18px}
.stButton button{border-radius:8px} [data-testid="stSidebar"] input{color:#163a60}
</style>''',unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def parsed_file(content):
    return core.parse_excel(content)

with st.sidebar:
    st.title('💧 Medição')
    st.caption('GESTÃO DO CONTRATO · LEITURAS')
    page=st.radio('Navegação',['Painel inicial','Importar planilhas','Fechamento mensal','Produtividade','Relatórios','Configurações'],label_visibility='collapsed')
    st.divider()
    reference=st.date_input('Mês de referência',value=date(2026,10,1),format='DD/MM/YYYY')
    month=reference.strftime('%Y-%m')
    st.caption('O dia selecionado não afeta o fechamento.')
    st.caption('Dados locais · Originais preservados')

info=storage.month_info(month);prices=info['prices'];rows=storage.records(month)
summary=core.summarize(rows,prices);total=sum(r['total_cents'] for r in summary)
active=[r for r in rows if not r['excluded']]
errors=sum(bool(r['result']['errors']) for r in active);conflicts=storage.conflicts(rows)
st.caption(f"CONTRATO SABESP · {month} · {'FECHADO' if info['closed'] else 'EM CONFERÊNCIA'}")
st.title(page)

def metrics():
    cols=st.columns(4)
    cols[0].metric('Faturamento mensal',money(total))
    cols[1].metric('Leituras faturáveis',f"{sum(r['Quantidade'] for r in summary if r['key'] in ('138','128','137')):,}".replace(',','.'))
    cols[2].metric('Registros ativos',f'{len(active):,}'.replace(',','.'))
    cols[3].metric('Pendências',errors+len(conflicts))

def summary_frame():
    return pd.DataFrame([{'Código':r['Código'],'Serviço':r['Categoria'],'Quantidade':r['Quantidade'],'Valor unitário':money(r['unit_cents']),'Total':money(r['total_cents'])} for r in summary])

def record_frame(selected):
    return pd.DataFrame([{'ID':r['id'],'Arquivo':r['name'],'Aba':r['sheet'],'Linha original':r['line'],'Funcionário':r['result']['employee'],'ATC':r['result']['city'],'Excluído':bool(r['excluded']),'Motivo':r['reason'],'Erros':'; '.join(r['result']['errors']),'Avisos':'; '.join(r['result']['alerts']),**{core.CATEGORIES[k][1]:v for k,v in r['result']['units'].items()}} for r in selected])

if page=='Painel inicial':
    st.write('Acompanhe o faturamento, a medição e as pendências do mês selecionado.')
    metrics()
    if not rows:st.info('Comece em Importar planilhas. Nenhum dado fictício foi carregado.')
    st.subheader('Composição do faturamento')
    st.dataframe(summary_frame(),hide_index=True,width='stretch')
    left,right=st.columns([3,2])
    with left:
        st.subheader('Quantidade por categoria')
        st.bar_chart(pd.DataFrame({'Serviço':[r['Categoria'] for r in summary],'Quantidade':[r['Quantidade'] for r in summary]}).set_index('Serviço'),color='#147D92')
    with right:
        st.subheader('Conferência do mês')
        st.write(f'**{len(storage.imports(month))}** abas importadas')
        st.write(f'**{sum(r["result"]["units"]["impressao"] for r in active)}** comunicados impressos')
        st.write(f'**{sum(r["result"]["units"]["apontamento"] for r in active)}** apontamentos operacionais')
        st.write(f'**{sum(bool(r["excluded"]) for r in rows)}** registros excluídos com justificativa')
        st.caption('Os adicionais podem incidir no mesmo registro de uma leitura; não são contados como novas leituras.')

elif page=='Importar planilhas':
    st.write('Importe uma aba por vez. O arquivo original é arquivado integralmente e identificado por SHA-256.')
    if info['closed']:st.warning('Este mês está fechado. Reabra em Fechamento mensal para importar.');st.stop()
    uploaded=st.file_uploader('Planilha de leitura (.xlsx)',type=['xlsx'])
    if uploaded:
        content=uploaded.getvalue()
        try:parsed=parsed_file(content)
        except Exception as e:st.error(f'Não foi possível ler a planilha: {e}');st.stop()
        selected=st.selectbox('Aba',[p['sheet'] for p in parsed]);p=next(p for p in parsed if p['sheet']==selected)
        st.success(f"{len(p['records']):,} registros · {len(p['headers'])} colunas · cabeçalho na linha {p['header_row']}".replace(',','.'))
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
        if st.button('Processar e importar',type='primary',disabled=not confirmed):
            try:
                with st.spinner('Preservando o original e processando os registros…'):added,skipped=storage.import_sheet(content,uploaded.name,p,mapping,month)
                st.success(f'Importação concluída: {added} registros inseridos; {skipped} duplicatas idênticas ignoradas.')
                st.session_state.pop('exports',None)
            except Exception as e:st.error(str(e))
    with st.expander('Arquivos importados e originais'):
        for entry in storage.imports(month):
            st.write(f"{entry['name']} · {entry['sheet']}")
            st.download_button('Baixar original intacto',(storage.DATA/'originais'/(entry['sha']+'.xlsx')).read_bytes(),file_name=entry['name'],key=f"original_{entry['id']}")

elif page=='Fechamento mensal':
    metrics();st.dataframe(summary_frame(),hide_index=True,width='stretch')
    if errors or conflicts:st.error(f'{errors} registros com erros e {len(conflicts)} chaves repetidas. Resolver ou excluir com justificativa antes de fechar. Totais com erros são zerados; chaves repetidas deixam a prévia pendente.')
    st.subheader('Conferência dos registros')
    category=st.selectbox('Categoria',['Todos',*[core.CATEGORIES[k][1] for k in core.CATEGORIES]])
    mode=st.selectbox('Exibir',['Todos','Com erros','Com avisos','Chaves repetidas','Excluídos'])
    selected=rows
    if category!='Todos':
        key=next(k for k,v in core.CATEGORIES.items() if v[1]==category);selected=[r for r in selected if r['result']['units'][key]>0]
    ids={i for group in conflicts for i in group}
    if mode=='Com erros':selected=[r for r in selected if r['result']['errors']]
    elif mode=='Com avisos':selected=[r for r in selected if r['result']['alerts']]
    elif mode=='Chaves repetidas':selected=[r for r in selected if r['id'] in ids]
    elif mode=='Excluídos':selected=[r for r in selected if r['excluded']]
    st.caption(f'{len(selected)} registros encontrados; linhas e arquivos de origem disponíveis.')
    st.dataframe(record_frame(selected),hide_index=True,width='stretch')
    with st.expander('Inspecionar dados originais / registrar decisão'):
        row_id=st.number_input('ID do registro',min_value=1,step=1)
        row=next((r for r in rows if r['id']==row_id),None)
        if row:
            st.dataframe(pd.DataFrame({'Coluna':list(row['raw']),'Valor original':[str(v) if v is not None else '' for v in row['raw'].values()]}),hide_index=True)
            reason=st.text_input('Justificativa da decisão')
            if st.button('Reincluir registro' if row['excluded'] else 'Excluir do faturamento',disabled=bool(info['closed'])):
                try:storage.exclude(month,row_id,reason,not bool(row['excluded']));st.session_state.pop('exports',None);st.rerun()
                except ValueError as e:st.error(str(e))
    if info['closed']:
        st.success(f"Fechamento registrado em UTC: {info['closed_at']}. Preços e importações bloqueados.")
        reason=st.text_input('Motivo de reabertura')
        if st.button('Reabrir mês'):
            try:storage.close_month(month,False,reason);st.session_state.pop('exports',None);st.rerun()
            except ValueError as e:st.error(str(e))
    else:
        confirmed=st.checkbox('Conferi os registros e aprovo o fechamento deste mês.')
        if st.button('Confirmar fechamento',type='primary',disabled=not confirmed or not rows or bool(errors or conflicts)):
            try:storage.close_month(month);st.session_state.pop('exports',None);st.rerun()
            except ValueError as e:st.error(str(e))
    with st.expander('Histórico de alterações'):st.dataframe(pd.DataFrame(storage.audit(month)),hide_index=True)

elif page=='Produtividade':
    st.write('Leituras faturáveis e adicionais separados. Registros excluídos não entram na produtividade.')
    dimension=st.radio('Agrupar por',['Funcionário','Unidade / cidade (ATC)'],horizontal=True)
    by='employee' if dimension=='Funcionário' else 'city';items=productivity(rows,prices,by)
    if not items:st.info('Importe a planilha para acompanhar a produtividade.');st.stop()
    frame=pd.DataFrame(items);label=frame.columns[0]
    goals=storage.settings().get('goals',{}).get(month,{})
    frame['Meta mensal de leituras']=[goals.get(by+'|'+str(v)) for v in frame[label]]
    frame['Atingimento (%)']=[round(100*r['Leituras faturáveis']/g,1) if g else None for r,g in zip(items,frame['Meta mensal de leituras'])]
    frame['Faturamento']=frame['total_cents'].map(money)
    st.dataframe(frame.drop(columns=['total_cents']),hide_index=True,width='stretch')
    st.subheader('Leituras faturáveis · 15 maiores volumes')
    st.bar_chart(frame.head(15).set_index(label)['Leituras faturáveis'],color='#147D92')
    st.caption('Meta em branco significa não definida. As metas são informadas pelo usuário; nenhuma meta é presumida.')
    with st.form('goal'):
        who=st.selectbox('Definir meta para',frame[label].tolist());target=st.number_input('Meta mensal de leituras faturáveis',min_value=0,step=1)
        if st.form_submit_button('Salvar meta'):
            all_goals=storage.settings().get('goals',{});all_goals.setdefault(month,{})
            if target:all_goals[month][by+'|'+who]=target
            else:all_goals[month].pop(by+'|'+who,None)
            storage.save_setting('goals',all_goals);st.rerun()

elif page=='Relatórios':
    st.write('Exporte o fechamento, produtividade e rastreabilidade. O Excel inclui todas as colunas importadas; o PDF traz indicadores, tabelas e gráfico.')
    metrics();st.dataframe(summary_frame(),hide_index=True,width='stretch')
    contract=storage.settings().get('contract',{})
    goals=storage.settings().get('goals',{}).get(month,{})
    signature=core.fingerprint({'month':month,'prices':prices,'closed':info['closed'],'rows':[(r['id'],r['excluded'],r['reason']) for r in rows],'contract':contract,'goals':goals})
    if st.button('Gerar Excel e PDF',type='primary',disabled=not rows):
        with st.spinner('Gerando relatórios com os dados reais…'):
            st.session_state['exports']=(signature,excel_report(month,rows,prices,storage.imports(month),storage.audit(month),contract,info['closed'],goals),pdf_report(month,rows,prices,contract,info['closed'],goals))
    generated=st.session_state.get('exports')
    if generated and generated[0]==signature:
        c1,c2=st.columns(2)
        c1.download_button('Baixar Excel',generated[1],file_name=f'fechamento-{month}.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
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
            if apply and rows and not info['closed']:storage.update_month_prices(month,new)
            st.session_state.pop('exports',None);st.success('Preços salvos. Meses fechados mantêm seus valores.');st.rerun()
    st.subheader('Regras confirmadas')
    st.markdown('''- R$ 1,38: impressa Sim, retida Não e causa vazia.
- R$ 1,28: impressa Não, retida Não e causa vazia.
- R$ 1,37: retida Não e causa preenchida, independentemente da impressão.
- Impressão: soma de Quantidade comunicados impressos × preço.
- Apontamento: cada CO1 Atual preenchido × preço, inclusive códigos de vistoria.
- Adicionais em todos os registros; registros sem data e releituras incluídos.
- Serviços de vistoria, feriado e demais itens de contrato não são faturados nesta versão.
- Arquivos idênticos não são reimportados no mesmo mês; linhas idênticas são ignoradas. Chaves fornecimento + data + tarefa repetidas exigem conferência antes de fechar.''')
    st.info('Faça backup de toda a pasta data com o sistema parado: ela contém o banco e os arquivos originais. Esta versão é local; não possui autenticação para exposição pública.')
