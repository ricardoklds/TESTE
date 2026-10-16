"""Interface consolidada: valores provisórios e aprovados explicitamente separados."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
import contract_finance as api
import inspection_billing as billing
from inspection_module_ui import money,service_frame
from contract_presentation import simulate,compose,table_rows

@st.cache_data(show_spinner=False,max_entries=32)
def cached_state(data,month,reading_version,inspection_version,closing_version):return api.state(data,month)


def render(data,month,allow_close=False):
    data=Path(data);root=data/'vistorias';bank=data/'contrato.sqlite3'
    # Identidades baratas do estado para invalidar cache; a consulta financeira permanece agregada.
    from contextlib import closing
    import sqlite3
    read_revision=None
    if bank.exists():
        with closing(sqlite3.connect(bank.resolve().as_uri()+'?mode=ro',uri=True)) as c:read_revision=c.execute('SELECT revision FROM cache_revision WHERE id=1').fetchone()[0]
    with api.connect(data) as c:version=tuple(c.execute('SELECT (SELECT COUNT(*) FROM closings),(SELECT COUNT(*) FROM deductions)').fetchone())
    p=cached_state(str(data),month,read_revision,billing.revision(root),version)
    st.title('Fechamento Geral' if allow_close else 'Painel Geral')
    if p['validated']:st.success('Fechamento Geral validado: fotografia mensal preservada.')
    else:st.warning('PRÉVIA DO CONTRATO — componentes ainda não validados não são definitivos.')
    cols=st.columns(3)
    cols[0].metric('Leituras',money(p['readings']['cents']));cols[1].metric('Vistorias',money(p['visits']['inspection_cents']));cols[2].metric('Geolocalização',money(p['visits']['geo']['cents']))
    st.caption('Leituras + Vistorias + Geolocalização = Fechamento bruto.')
    enabled=st.toggle('Aplicar multa de 1%',value=False,key='simulate_fine:'+month) if allow_close else False
    simulated=simulate(p['gross_cents'],enabled)
    cols=st.columns(3)
    if allow_close:
        cols[0].metric('Fechamento bruto',money(simulated['gross_cents']));cols[1].metric('Glosa simulada',money(simulated['deduction_cents']));cols[2].metric('Fechamento líquido simulado',money(simulated['net_cents']))
        st.caption('Simulação gerencial. Desligar o controle retira o desconto da visualização; nenhum valor é registrado no fechamento oficial.')
    else:
        cols[0].metric('Fechamento bruto',money(p['gross_cents']));cols[1].metric('Glosa definitiva registrada',money(p['deduction']['cents'] if p['deduction'] else 0));cols[2].metric('Líquido oficial' if p['validated'] else 'Líquido provisório',money(p['net_cents']))
    composition=None
    if allow_close:
        try:composition=compose(data,p)
        except ValueError as e:st.warning(str(e))
        if composition:
            st.metric('Subtotal informativo · Vistorias + Geolocalização',money(composition['visits_geo_cents']))
            st.caption('Subtotal informativo; não é somado novamente ao fechamento bruto.')
        with st.expander('Composição do Faturamento'):
            if composition:
                st.dataframe(pd.DataFrame(table_rows(composition)),hide_index=True)
                st.dataframe(pd.DataFrame([{'Componente':k,'Subtotal':money(v)} for k,v in composition['subtotals'].items()]),hide_index=True)
                st.caption('Quantidades são faturáveis por serviço. Adicionais podem se acumular: não somar como fornecimentos distintos ou registros operacionais.')
                if not composition['complete']:st.warning(composition['notes'][0])
    else:
        with st.expander('Detalhes por categoria'):
            st.dataframe(service_frame(p['visits']['services']),hide_index=True)
            st.caption('Geolocalização é contabilizada uma única vez no componente separado acima.')
    if allow_close and composition:
        formats=st.selectbox('Formato da prévia',['PDF e Excel','PDF','Excel'])
        preview_scope=(month,billing.digest(p),enabled,formats)
        if st.button('Gerar relatório de prévia'):
            import contract_reports
            with st.spinner('Preparando prévia gerencial dos totais existentes…'):
                artifacts={}
                if formats in ('PDF e Excel','PDF'):artifacts['PDF']=contract_reports.pdf(composition,enabled)
                if formats in ('PDF e Excel','Excel'):artifacts['Excel']=contract_reports.excel(composition,enabled)
                st.session_state['managerial_contract_preview']=(preview_scope,artifacts)
        saved_preview=st.session_state.get('managerial_contract_preview')
        if saved_preview and saved_preview[0]==preview_scope:
            st.caption('PRÉVIA — NÃO APROVADA. A exportação não altera o status dos fechamentos.')
            for kind,content in saved_preview[1].items():
                st.download_button('Baixar prévia '+kind,content,file_name='previa-contrato-'+month+('.pdf' if kind=='PDF' else '.xlsx'),mime='application/pdf' if kind=='PDF' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',on_click='ignore')
    if not p['readings']['closed']:st.info('Leituras ainda não estão fechadas na competência. Utilize o módulo de Leituras.')
    if not p['visits']['approved']:st.info('Vistorias/Geolocalização ainda não foram aprovadas após conciliação.')
    if not allow_close:return
    if not p['validated']:
        with st.form('approve_contract'):
            submit=st.form_submit_button('Validar Fechamento Geral',disabled=not p['ready'])
        if submit:
            try:api.approve(data,month,billing.digest({k:v for k,v in p.items() if k not in ('validated','deduction','net_cents')}),confirmed=True);st.rerun()
            except ValueError as e:st.error(str(e))
    else:
        with st.expander('Registro definitivo de glosa · fechamento oficial'):
            st.write('Glosa definitiva registrada: '+money(p['deduction']['cents'] if p['deduction'] else 0))
            st.write('Líquido oficial: '+money(p['net_cents']))
            st.caption('Histórico somente para consulta. O controle de 1% acima é apenas uma simulação gerencial.')
    st.caption('O relatório do contrato preserva os valores oficiais; não incorpora a glosa simulada.')
    if st.button('Preparar relatório do contrato'):
        from io import BytesIO
        import openpyxl
        from fast_reports import text_row
        w=openpyxl.Workbook(write_only=True);s=w.create_sheet('Contrato');text_row(s,['Competência','Situação','Leituras (R$)','Vistorias (R$)','Geolocalização (R$)','Fechamento bruto (R$)','Glosa definitiva (R$)','Líquido oficial (R$)'])
        from openpyxl.cell import WriteOnlyCell
        amounts=[p['readings']['cents'],p['visits']['inspection_cents'],p['visits']['geo']['cents'],p['gross_cents'],p['deduction']['cents'] if p['deduction'] else 0,p['net_cents']]
        cells=[]
        for value in amounts:
            cell=WriteOnlyCell(s,value=value/100);cell.number_format='"R$" #,##0.00';cells.append(cell)
        s.append([month,'Validado' if p['validated'] else 'Provisório',*cells]);b=BytesIO();w.save(b)
        st.session_state['contract_export']=(month,read_revision,billing.revision(root),version,b.getvalue())
    saved=st.session_state.get('contract_export')
    if saved and saved[:4]==(month,read_revision,billing.revision(root),version):st.download_button('Baixar relatório do contrato',saved[4],file_name=f'contrato-{month}.xlsx',on_click='ignore')
    with st.expander('Histórico do contrato'):
        with api.connect(data) as c:history=[dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 50')]
        st.dataframe(pd.DataFrame(history).rename(columns={'id':'Registro','created':'Data e hora (UTC)','action':'Ação','payload':'Detalhes'}),hide_index=True)
