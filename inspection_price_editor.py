"""Tabela de preços: edita somente propostas; persistência atômica após confirmação."""
from decimal import Decimal,InvalidOperation
import pandas as pd
import streamlit as st
import inspection_billing as api

def price_cents(value):
    try:d=Decimal(str(value))
    except (InvalidOperation,ValueError):raise ValueError('Informe um preço numérico válido.')
    if not d.is_finite() or d<0 or d*100!=(d*100).to_integral_value():raise ValueError('Preço não negativo, com no máximo duas casas decimais.')
    return int(d*100)

def changes_from_table(original,edited,month):
    if len(original)!=len(edited):raise ValueError('Use Adicionar serviço para novas linhas; serviços não são excluídos.')
    changes=[]
    for old,new in zip(original,edited):
        if old['code']!=new['Código'] or old['name']!=new['Descrição']:raise ValueError('Código e descrição existentes devem ser preservados.')
        amount=price_cents(new['Valor unitário (R$)']);effective=str(new['Vigência']);api.month_bounds(effective)
        active=new['Situação']=='Ativo'
        if new['Situação'] not in ('Ativo','Inativo'):raise ValueError('Situação inválida.')
        if amount!=old['cents'] or active!=bool(old['active']) or effective!=month:
            changes.append({'code':old['code'],'name':old['name'],'cents':amount,'active':active,'effective':effective})
    return changes

def render(root,month,services):
    revision=api.revision(root)
    base=[{'Código':r['code'],'Descrição':r['name'],'Valor unitário (R$)':r['cents']/100,'Vigência':month,'Situação':'Ativo' if r['active'] else 'Inativo'} for r in services]
    st.caption('Edite preço, vigência ou situação. Vigência proposta inicia na competência selecionada. Salvar prepara a conferência; nenhuma alteração é aplicada sem confirmar.')
    edited=st.data_editor(pd.DataFrame(base),hide_index=True,num_rows='fixed',disabled=['Código','Descrição'],width='stretch',key=f'prices:{root}:{month}:{revision}',column_config={
        'Valor unitário (R$)':st.column_config.NumberColumn('Valor unitário (R$)',min_value=0,step=0.01,format='R$ %.2f',required=True),
        'Vigência':st.column_config.TextColumn('Vigência',help='Competência de início: AAAA-MM',required=True),
        'Situação':st.column_config.SelectboxColumn('Situação',options=['Ativo','Inativo'],required=True)})
    if st.button('Salvar alterações'):
        try:
            changes=changes_from_table(services,edited.to_dict('records'),month)
            if not changes:st.info('Nenhuma alteração na tabela.')
            else:
                change={'kind':'services','effective':min(r['effective'] for r in changes),'changes':changes,'evidence':'Alteração confirmada na tabela de serviços e preços.'}
                with st.spinner('Conferindo vigências e impacto financeiro…'):st.session_state['catalog_plan']=api.prepare_change(root,change)
        except ValueError as e:st.error(str(e))
    if st.button('Adicionar serviço'):st.session_state['new_service:'+root]=not st.session_state.get('new_service:'+root,False)
    if st.session_state.get('new_service:'+root):
        with st.form('new_price_service'):
            code=st.text_input('Código do novo serviço');name=st.text_input('Descrição do novo serviço')
            amount=st.number_input('Valor unitário do novo serviço (R$)',min_value=0.0,value=None,step=0.01)
            effective=st.text_input('Vigência do novo serviço',value=month)
            if st.form_submit_button('Salvar novo serviço'):
                try:
                    with api.connect(root) as c:exists=c.execute('SELECT 1 FROM services WHERE code=?',(code.strip(),)).fetchone()
                    if exists:raise ValueError('Código já cadastrado; edite a linha existente.')
                    change={'kind':'service','code':code.strip(),'name':name.strip(),'effective':effective,'cents':price_cents(amount),'active':True,'evidence':'Inclusão confirmada pela tabela de serviços e preços.'}
                    with st.spinner('Conferindo inclusão e vigência…'):st.session_state['catalog_plan']=api.prepare_change(root,change)
                except ValueError as e:st.error(str(e))
    with st.expander('Preços e vigências cadastrados'):
        with api.connect(root) as c:
            rows=[dict(r) for r in c.execute('SELECT s.code,s.name,p.* FROM services s JOIN prices p ON p.code=s.code ORDER BY s.code,p.effective DESC')]
        st.dataframe(pd.DataFrame([{'Código':r['code'],'Descrição':r['name'],'Valor unitário (R$)':r['cents']/100,'Vigência':r['effective'],'Situação':'Ativo' if r['active'] else 'Inativo'} for r in rows]),hide_index=True,column_config={'Valor unitário (R$)':st.column_config.NumberColumn(format='R$ %.2f')})
