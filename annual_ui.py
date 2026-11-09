"""Página anual isolada das telas financeiras já existentes."""
import streamlit as st
import pandas as pd
import altair as alt
import annual_billing as api
import annual_reports as reports
from contract_presentation import money

@st.cache_data(show_spinner=False,max_entries=8)
def cached_months(data,year,revision):
    rows=api.monthly(data,f'{year-1:04d}-02',f'{year:04d}-12')
    if api.version(data,False)!=revision:raise ValueError('Dados alterados durante a consulta; atualize a página para obter uma visão consistente.')
    return rows

def render(data,reference):
    st.title('Faturamento Anual')
    st.caption('Valores brutos do contrato, sem glosa simulada. Meses provisórios e incompletos são identificados separadamente.')
    year=st.number_input('Ano de referência',min_value=1901,max_value=9998,value=int(reference[:4]),step=1,key='annual_year')
    window=st.selectbox('Média móvel (meses)',[3,6,12],key='annual_window')
    try:
        report_version=api.version(data)
        history=api.goals(data)
        with st.spinner('Consultando totais mensais existentes…'):months=cached_months(str(data),year,api.version(data,False))
        report=api.analyze(months,year,window,history)
        if api.version(data)!=report_version:raise ValueError('Histórico alterado durante a leitura; atualize a página.')
    except Exception as e:
        st.error('Não foi possível consultar o histórico anual. Nenhum banco foi alterado. '+str(e));return
    with st.expander('Meta mensal gerencial'):
        st.caption('Referência inicial: R$ 650.000,00. Alterações não modificam faturamento nem fechamentos; cada gravação fica no histórico.')
        with st.form('annual_goal'):
            effective=st.text_input('Início de vigência (AAAA-MM)',value=f'{year:04d}-01')
            value=st.number_input('Meta mensal (R$)',min_value=0.01,value=api.target(history,f'{year:04d}-01')/100,step=1000.,format='%.2f')
            save=st.form_submit_button('Salvar meta')
        if save:
            try:api.save_goal(data,effective,value);st.success('Meta gerencial salva.');st.rerun()
            except (ValueError,OSError) as e:st.error(str(e))
        if history:st.dataframe(pd.DataFrame([{'Vigência':r['effective'],'Meta':money(r['cents']),'Salvo em (UTC)':r['created']} for r in history]),hide_index=True)
    cols=st.columns(3)
    for col,label,key in zip(cols,['Acumulado disponível','Aprovado','Provisório/parcial'],['accumulated_cents','approved_cents','provisional_cents']):col.metric(label,money(report[key]))
    st.caption('Acumulado disponível inclui valores conhecidos de meses incompletos. Composição completa significa componentes disponíveis e sem pendências financeiras; não comprova cobertura de todos os grupos.')
    current=report['current'];cols=st.columns(3)
    cols[0].metric('Média móvel atual',money(current['rolling_cents']) if current and current['rolling_cents'] is not None else 'Histórico insuficiente')
    cols[1].metric('Média móvel − meta vigente',money(current['rolling_difference_cents']) if current and current['rolling_difference_cents'] is not None else '—')
    cols[2].metric('Média dos meses com composição completa',money(report['average_cents']) if report['average_cents'] is not None else '—')
    if current:st.caption(f"Última competência com dados: {current['month']} · {current['status']} · Média móvel: {current['rolling_status']}")
    for label,key in [('Melhor mês completo','best'),('Pior mês completo','worst')]:
        r=report[key];st.caption(label+': '+(r['month']+' · '+money(r['gross_cents']) if r else 'Indisponível'))
    if current:st.caption('Variação em relação ao mês anterior: '+(money(current['previous_difference_cents']) if current['previous_difference_cents'] is not None else 'Indisponível: competências completas consecutivas necessárias.'))
    component=st.selectbox('Visualizar componente',['Total do contrato','Leituras','Vistorias','Geolocalização'])
    key={'Total do contrato':'gross_cents','Leituras':'readings_cents','Vistorias':'visits_cents','Geolocalização':'geo_cents'}[component]
    chart=pd.DataFrame([{'Competência':r['month'],'Faturamento':r[key]/100 if r[key] is not None else None,'Meta':r['target_cents']/100,'Média móvel do bruto':r['rolling_cents']/100 if r['rolling_cents'] is not None else None,'Resultado':'Sem dados' if r[key] is None else 'Incompleto' if not r['complete'] else 'Meta atingida' if r['gross_cents']>=r['target_cents'] else 'Abaixo da meta','Situação':r['status']} for r in report['rows']])
    base=alt.Chart(chart).encode(x=alt.X('Competência:N',sort='ascending'))
    bars=base.mark_bar().encode(y=alt.Y('Faturamento:Q',title='Valor (R$)'),color=alt.Color('Resultado:N',scale=alt.Scale(domain=['Meta atingida','Abaixo da meta','Incompleto','Sem dados'],range=['#248764','#326fa8','#94a3b8','#dce5ee'])),tooltip=['Competência','Faturamento','Situação'])
    goal=base.mark_line(strokeDash=[6,4],color='#d18b19').encode(y='Meta:Q',tooltip=['Competência','Meta'])
    rolling=base.mark_line(color='#8b4db5',point=True).encode(y='Média móvel do bruto:Q',tooltip=['Competência','Média móvel do bruto'])
    st.altair_chart(bars+goal+rolling,use_container_width=True)
    st.caption('Linha tracejada dourada: meta do contrato. Linha roxa: média móvel do bruto total, inclusive ao visualizar um componente. Cores de atingimento referem-se ao bruto mensal, não à média móvel.')
    frame=pd.DataFrame([{label:reports.display(r[k],k) for k,label in reports.COLUMNS} for r in report['rows']]);st.dataframe(frame,hide_index=True,width='stretch')
    if st.button('Gerar relatórios anuais PDF e Excel'):
        with st.spinner('Gerando relatórios dos totais exibidos…'):
            st.session_state['annual_exports']=(year,window,report_version,reports.excel(report),reports.pdf(report))
    saved=st.session_state.get('annual_exports')
    if saved and saved[:3]==(year,window,api.version(data)):
        st.download_button('Baixar Excel anual',saved[3],file_name=f'faturamento-anual-{year}.xlsx',mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',on_click='ignore')
        st.download_button('Baixar PDF anual',saved[4],file_name=f'faturamento-anual-{year}.pdf',mime='application/pdf',on_click='ignore')
