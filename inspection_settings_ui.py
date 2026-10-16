"""Configuração municipal exclusivamente das Vistorias, com confirmação de impacto."""
from pathlib import Path
import pandas as pd
import streamlit as st
import inspection_billing as api
import inspection_contract
from inspection_module_ui import money

def render(data,month):
    root=str(Path(data)/'vistorias');st.title('Municípios do Contrato · Vistorias')
    with api.connect(root) as c:policy=inspection_contract.policy(c,month)
    st.caption('Esta configuração não afeta Leituras. Vigência inicial setembro/2026 e competências futuras; municípios desconhecidos não pertencem automaticamente ao contrato.')
    with st.form('contract_scope'):
        allowed=st.text_area('Municípios autorizados (um por linha)',value='\n'.join(policy['allowed']))
        excluded=st.text_area('Municípios fora do contrato (um por linha)',value='\n'.join(policy['excluded']))
        effective=st.text_input('Início de vigência (AAAA-MM)',value=month)
        if st.form_submit_button('Calcular impacto do escopo'):
            try:
                change={'kind':'scope','allowed':allowed.splitlines(),'excluded':excluded.splitlines(),'effective':effective}
                with st.spinner('Calculando impacto financeiro e operacional…'):st.session_state['contract_scope_plan']=api.prepare_change(root,change)
            except ValueError as e:st.error(str(e))
    plan=st.session_state.get('contract_scope_plan')
    if plan and plan['root']==str(Path(root).resolve()):
        st.write('Prévia: nenhuma mudança de escopo foi salva.');st.write({k:v for k,v in plan['change'].items() if k!='evidence'})
        st.dataframe(pd.DataFrame([{'Competência':r['month'],'Vistorias antes':money(r['before']['inspection_cents']),'Vistorias depois':money(r['after']['inspection_cents']),'Diferença em centavos':r['delta_cents'],'Ocorrências contratuais antes':r['before']['deadline']['total'],'Ocorrências contratuais depois':r['after']['deadline']['total'],'% prazo antes':r['before']['deadline']['percent'],'% prazo depois':r['after']['deadline']['percent']} for r in plan['impact']]),hide_index=True)
        with st.form('confirm_scope'):
            submit=st.form_submit_button('Confirmar escopo')
        if submit:
            try:api.confirm_change(root,plan,True);st.session_state.pop('contract_scope_plan',None);st.rerun()
            except ValueError as e:st.error(str(e))
    page=st.number_input('Página do histórico de escopo',min_value=1,step=1)
    with api.connect(root) as c:
        versions=[dict(r) for r in c.execute("SELECT key,value FROM metadata WHERE key LIKE 'contract_scope:%' ORDER BY key")]
        history=[dict(r) for r in c.execute("SELECT * FROM audit WHERE action='Alteração de catálogo confirmada' AND json_extract(payload,'$.change.kind')='scope' ORDER BY id DESC LIMIT 50 OFFSET ?",((page-1)*50,))]
    st.dataframe(pd.DataFrame(versions),hide_index=True)
    st.dataframe(pd.DataFrame(history),hide_index=True)
