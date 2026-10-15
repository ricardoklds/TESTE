"""Interface consolidada: valores provisórios e aprovados explicitamente separados."""
import json
from pathlib import Path
import pandas as pd
import streamlit as st
import contract_finance as api
import inspection_billing as billing
from inspection_module_ui import money

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
    st.dataframe(pd.DataFrame(p['visits']['services']),hide_index=True)
    cols=st.columns(3);cols[0].metric('Faturamento bruto mensal' if p['validated'] else 'Bruto apurado · provisório',money(p['gross_cents']));cols[1].metric('Glosa aplicada',money(p['deduction']['cents'] if p['deduction'] else 0));cols[2].metric('Líquido' if p['validated'] else 'Líquido · provisório',money(p['net_cents']))
    st.caption('Leituras + Vistorias + Geolocalização = bruto. Não há dupla contagem entre total e municípios da geolocalização.')
    if not p['readings']['closed']:st.info('Leituras ainda não estão fechadas na competência. Utilize o módulo de Leituras.')
    if not p['visits']['approved']:st.info('Vistorias/Geolocalização ainda não foram aprovadas após conciliação.')
    if not allow_close:return
    if not p['validated']:
        with st.form('approve_contract'):
            evidence=st.text_input('Documento e responsável pelo fechamento geral');yes=st.checkbox('Confirmo a consolidação mensal completa e validada')
            submit=st.form_submit_button('Validar Fechamento Geral',disabled=not p['ready'])
        if submit:
            try:api.approve(data,month,billing.digest({k:v for k,v in p.items() if k not in ('validated','deduction','net_cents')}),evidence,yes);st.rerun()
            except ValueError as e:st.error(str(e))
    else:
        snapshot={k:v for k,v in p.items() if k not in ('validated','deduction','net_cents')};deadline=p['deadline']
        eligible=deadline['total'] and not deadline['met'] and not deadline['pending']
        if eligible:st.warning(f"Pontualidade: {deadline['percent']:.2f}%. Possível glosa de 1% sobre o Fechamento Geral. Nenhuma aplicação automática.")
        else:st.info('Sem condição apurada para glosa definitiva (meta atingida ou prazo não validado).')
        if st.button('Aplicar multa',disabled=not eligible or p['deduction'] is not None):st.session_state['contract_fine_scope']=(month,billing.digest(snapshot))
        if st.session_state.get('contract_fine_scope')==(month,billing.digest(snapshot)) and not p['deduction']:
            st.write('Base total validada: '+money(p['gross_cents']))
            with st.form('contract_fine_confirm'):
                evidence=st.text_input('Documento e justificativa da glosa');yes=st.checkbox('Confirmo aplicar e registrar glosa de 1% sobre o Fechamento Geral validado')
                submit=st.form_submit_button('Confirmar aplicação da multa')
            if submit:
                try:api.apply_fine(data,month,billing.digest(snapshot),evidence,yes);st.session_state.pop('contract_fine_scope',None);st.rerun()
                except ValueError as e:st.error(str(e))
    if st.button('Preparar relatório do contrato'):
        from io import BytesIO
        import openpyxl
        from fast_reports import text_row
        w=openpyxl.Workbook(write_only=True);s=w.create_sheet('Contrato');text_row(s,['Competência','Situação','Leituras centavos','Vistorias centavos','Geolocalização centavos','Bruto centavos','Glosa centavos','Líquido centavos'])
        text_row(s,[month,'Validado' if p['validated'] else 'Provisório',p['readings']['cents'],p['visits']['inspection_cents'],p['visits']['geo']['cents'],p['gross_cents'],p['deduction']['cents'] if p['deduction'] else 0,p['net_cents']]);b=BytesIO();w.save(b)
        st.session_state['contract_export']=(month,read_revision,billing.revision(root),version,b.getvalue())
    saved=st.session_state.get('contract_export')
    if saved and saved[:4]==(month,read_revision,billing.revision(root),version):st.download_button('Baixar relatório do contrato',saved[4],file_name=f'contrato-{month}.xlsx',on_click='ignore')
    with st.expander('Histórico do contrato'):
        with api.connect(data) as c:history=[dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 50')]
        st.dataframe(pd.DataFrame(history),hide_index=True)
