"""Menu expansível; os rótulos públicos preservam as rotas internas de Leituras."""
MODULES=['Painel geral','Leituras','Vistorias','Fechamento geral','Configurações']
PAGES={'Leituras':['Painel inicial','Importar planilhas','Fechamento mensal','Produtividade','Relatórios'],
'Vistorias':['Painel de Vistorias','Importação de Vistorias','Prazos e Meta Contratual','Geolocalização','Faturamento de Vistorias','Relatórios de Vistorias'],
'Painel geral':['Visão consolidada do contrato'],'Fechamento geral':['Consolidação financeira mensal'],
'Configurações':['Serviços e Preços de Vistorias','Municípios do Contrato','Regras comerciais de Vistorias','Configurações']}
LABELS={'Painel inicial':'Painel de Leituras','Importar planilhas':'Importação de Leituras','Fechamento mensal':'Fechamento de Leituras','Relatórios':'Relatórios de Leituras','Configurações':'Configurações de Leituras'}

def select(st,module,page):
    st.session_state['active_module']=module
    st.session_state['active_page']=page

def sidebar(st):
    module=st.session_state.get('active_module','Leituras');page=st.session_state.get('active_page',PAGES.get(module,['Painel inicial'])[0])
    if page not in PAGES.get(module,[]):module,page='Leituras','Painel inicial'
    def link(module_,page_,label):
        st.button(label,key='nav:'+module_+':'+page_,width='stretch',type='primary' if (module_,page_)==(module,page) else 'secondary',on_click=select,args=(st,module_,page_))
    link('Painel geral',PAGES['Painel geral'][0],'Painel Geral')
    for group in ['Leituras','Vistorias']:
        # Expansão nativa no navegador: abrir/recolher não executa consultas Python.
        with st.expander(group,expanded=module==group):
            for entry in PAGES[group]:link(group,entry,LABELS.get(entry,entry))
    link('Fechamento geral',PAGES['Fechamento geral'][0],'Fechamento Geral')
    with st.expander('Configurações',expanded=module=='Configurações'):
        for entry in PAGES['Configurações']:link('Configurações',entry,LABELS.get(entry,entry))
    return module,page
