"""Navegação modular. Mantém nomes internos das telas auditadas de Leituras."""
MODULES=['Painel geral','Leituras','Vistorias','Fechamento geral','Configurações']
PAGES={'Leituras':['Painel inicial','Importar planilhas','Fechamento mensal','Produtividade','Relatórios'],
'Vistorias':['Painel de Vistorias','Importação de Vistorias','Prazos e Meta Contratual','Serviços e Tabela de Preços','Geolocalização','Faturamento de Vistorias','Relatórios de Vistorias'],
'Painel geral':['Visão consolidada do contrato'],'Fechamento geral':['Consolidação financeira mensal'],'Configurações':['Configurações','Municípios do Contrato']}
LABELS={'Painel inicial':'Painel de Leituras','Importar planilhas':'Importação de Leituras','Fechamento mensal':'Fechamento de Leituras','Relatórios':'Relatórios de Leituras'}
def sidebar(st):
    module=st.selectbox('Módulo',MODULES,index=1,key='active_module')
    page=st.radio('Navegação',PAGES[module],format_func=lambda p:LABELS.get(p,p),label_visibility='collapsed')
    return module,page
