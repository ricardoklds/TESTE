"""Componentes gerenciais, separados das ações do fechamento oficial."""
import pandas as pd
import streamlit as st
import cached_queries as cached
import managerial
import periods
import queries
from exports import money


@st.fragment(run_every='30s')
def render(path,revision,month,prices,start=None,end=None,report_period=False):
    if queries.revision()!=revision:st.rerun()
    if report_period:
        first,last=periods.month_bounds(month)
        mode=st.radio('Período do relatório gerencial',['Mês completo','Dia específico','Intervalo personalizado'],horizontal=True,key='manager_report_mode')
        begin,finish=first,last
        if mode=='Dia específico':begin=finish=st.date_input('Dia gerencial',first,min_value=first,max_value=last,key='manager_report_day_'+month)
        elif mode=='Intervalo personalizado':
            a,b=st.columns(2);begin=a.date_input('Início gerencial',first,min_value=first,max_value=last,key='manager_report_start_'+month);finish=b.date_input('Fim gerencial',last,min_value=first,max_value=last,key='manager_report_end_'+month)
        try:start,end=periods.query_bounds(month,mode,begin,finish)
        except ValueError as e:st.error(str(e));return
    opts=cached.management_options(path,revision,month)
    keys={k:'manager_'+k+'_'+month for k in managerial.DIMS}
    if st.button('Todos — limpar filtros gerenciais',key='manager_clear'):
        for key in keys.values():st.session_state[key]=[]
    cols=st.columns(3);filters={}
    for col,key in zip(cols,managerial.DIMS):
        # Uma seleção sem movimento no período deve resultar em zero, nunca virar Todos.
        choices=sorted(set(opts[key])|set(st.session_state.get(keys[key],[])))
        filters[key]=tuple(sorted(col.multiselect(managerial.LABELS[key],choices,key=keys[key],placeholder='Todos')))
    st.caption('Sem seleção = Todos. Filtros combinam cidade/ATC, grupo e funcionário; não alteram o fechamento oficial. Localidade e funcionário seguem os dados informados, sem suposições.')
    data=cached.management_overview(path,revision,month,prices,start,end,filters)
    # Total primeiro mantém a leitura do indicador principal; os três valores são separados.
    cols=st.columns(3)
    for col,label,key in zip(cols,['Faturamento total','Leituras e adicionais normais','Adicional de feriados'],['total_cents','normal_cents','holiday_cents']):col.metric(label,money(data[key]))
    a,b,c=st.columns(3);a.metric('Leituras faturáveis',f'{data["readings"]:,}'.replace(',','.'));b.metric('Registros processados',f'{data["records"]:,}'.replace(',','.'));c.metric('Registros sem data na seleção',f'{data["undated"]:,}'.replace(',','.'))
    st.caption('Registros processados: registros ativos da seleção, inclusive com erros; leituras faturáveis e valores mantêm os critérios financeiros existentes.')
    if data['undated']:st.warning(f'{data["undated"]} registros sem data permanecem no acumulado mensal da seleção. Filtros por dia e intervalo os deixam fora da visualização.')
    if data['errors']:st.warning(f'{data["errors"]} registros ativos com erros na seleção. Não foram corrigidos automaticamente.')
    summary=queries.summary({'units':{k:data[v] for k,v in managerial.UNITS.items() if k!='feriado'},'holiday_quantity':data['fee']},prices)
    st.subheader('Composição do faturamento gerencial')
    st.dataframe(pd.DataFrame([{'Serviço':r['Categoria'],'Quantidade':r['Quantidade'],'Unitário':money(r['unit_cents']),'Total':money(r['total_cents'])} for r in summary]),hide_index=True,width='stretch')
    n,ranking=cached.management_page(path,revision,month,prices,start,end,filters)
    st.subheader('Ranking por funcionário — 50 maiores volumes')
    def frame(rows,dimensions):
        return pd.DataFrame([{**{managerial.LABELS[k]:r[k] for k in dimensions},'Registros processados':r['records'],'Leituras faturáveis':r['readings'],
            'Normais':money(r['normal_cents']),'Feriados':money(r['holiday_cents']),'Faturamento total':money(r['total_cents'])} for r in rows])
    if ranking:
        st.dataframe(frame(ranking,('employee',)),hide_index=True,width='stretch')
        st.bar_chart(pd.DataFrame([{'Funcionário':r['employee'],'Leituras faturáveis':r['readings']} for r in ranking[:15]]).set_index('Funcionário'),color='#147D92')
    else:st.info('Nenhum registro corresponde à seleção.')
    st.caption(f'{n} funcionários/categorias na seleção. Os indicadores incluem todos; o ranking mostra até 50. Empates são ordenados pelo nome.')
    st.subheader('Detalhamento por cidade/ATC, grupo e funcionário')
    count,first=cached.management_page(path,revision,month,prices,start,end,filters,('city','group','employee'),0,100)
    # Chave inclui o escopo; novas importações ou filtros reiniciam a paginação.
    import hashlib,json
    scope=hashlib.sha256(json.dumps([revision,month,start,end,filters],sort_keys=True).encode()).hexdigest()[:16]
    page=int(st.number_input('Página gerencial',min_value=1,max_value=max(1,(count+99)//100),value=1,step=1,key='manager_page_'+scope))
    rows=first if page==1 else cached.management_page(path,revision,month,prices,start,end,filters,('city','group','employee'),(page-1)*100,100)[1]
    if rows:st.dataframe(frame(rows,('city','group','employee')),hide_index=True,width='stretch')
    st.caption(f'{count} combinações; até 100 por página. As dimensões são detalhamentos das mesmas leituras, não novas cobranças.')
    if st.button('Gerar Excel e PDF gerenciais da seleção',key='manager_excel'):
        with st.spinner('Gerando agregados gerenciais…'):
            try:
                content=managerial.excel(path,month,prices,start,end,filters,revision)
                document=managerial.pdf(data,month,start,end,filters,ranking,first)
                st.session_state['manager_export']=(scope,content,document)
            except Exception as e:st.error(str(e))
    generated=st.session_state.get('manager_export')
    if generated and generated[0]==scope:
        a,b=st.columns(2)
        a.download_button('Baixar Excel gerencial',generated[1],file_name=f'gerencial-{month}.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        b.download_button('Baixar PDF gerencial',generated[2],file_name=f'gerencial-{month}.pdf',mime='application/pdf')
    st.caption('Excel gerencial: todos os agregados da seleção, sem limite de 50/100. Exportações oficiais mensais permanecem separadas.')
    if queries.revision()!=revision:st.rerun()
    return data
