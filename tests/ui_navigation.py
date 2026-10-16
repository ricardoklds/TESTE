"""Ações do menu público usadas pelos testes de integração Streamlit."""
def navigate(app,page=None,module=None):
    if page=='Serviços e Tabela de Preços':module,page='Configurações','Serviços e Preços de Vistorias'
    if page is None:
        page={'Leituras':'Painel inicial','Vistorias':'Painel de Vistorias','Configurações':'Configurações','Painel geral':'Visão consolidada do contrato','Fechamento geral':'Consolidação financeira mensal'}[module]
    if module is None:
        if page in ['Serviços e Preços de Vistorias','Municípios do Contrato','Regras comerciais de Vistorias','Configurações']:module='Configurações'
        elif page in ['Painel de Vistorias','Importação de Vistorias','Prazos e Meta Contratual','Produtividade de Vistorias','Geolocalização','Faturamento de Vistorias','Relatórios de Vistorias']:module='Vistorias'
        else:module='Leituras'
    next(b for b in app.sidebar.button if b.key=='nav:'+module+':'+page).click().run()
    return app


def set_month(app,value):
    app.sidebar.number_input(key='reference_year').set_value(value.year)
    app.sidebar.selectbox(key='reference_month').set_value(value.month)
    return app
