"""Interface modular das vistorias; nenhuma dependência do banco de Leituras."""
from pathlib import Path
from decimal import Decimal,InvalidOperation
import json
import pandas as pd
import streamlit as st
import inspection_billing as api

@st.cache_data(show_spinner=False,max_entries=32)
def cached_preview(root,month,revision):return api.financial(root,month)
@st.cache_data(show_spinner=False,max_entries=32)
def cached_details(root,month,revision,offset):return api.detail_page(root,month,offset)
@st.cache_data(show_spinner=False,max_entries=2)
def workbook_sheets(content):
    import inspections
    return inspections.sheets(content)

def cents(text):
    d=Decimal(text.replace('.','').replace(',','.'))
    if not d.is_finite() or d<0 or d*100!=(d*100).to_integral_value():raise ValueError('Preço deve ser não negativo, com até duas casas decimais.')
    return int(d*100)
def money(c):return f'R$ {c/100:,.2f}'.replace(',','_').replace('.',',').replace('_','.')

def render(data,month,page):
    root=str(Path(data)/'vistorias')
    if page=='Prazos e Meta Contratual':
        import inspections_ui
        inspections_ui.render(data,month,show_import=False,show_fine=False)
        st.info('A glosa definitiva é aplicada exclusivamente no Fechamento Geral validado.')
        with st.expander('Simulações históricas de multa (não são glosas aplicadas)'):
            import inspections
            with inspections.connect(root) as c:history=[dict(r) for r in c.execute('SELECT id,created,payload FROM penalties ORDER BY id DESC LIMIT 50')]
            st.dataframe(pd.DataFrame(history),hide_index=True)
        return
    st.title(page)
    st.caption('Vistorias: originais próprios, competência pela conclusão, financeiro separado de Leituras.')
    if page=='Importação de Vistorias':
        import_panel(root);return
    if page=='Serviços e Tabela de Preços':
        catalog(root,month);return
    if page=='Geolocalização':
        geolocation(root,month);return
    revision=api.revision(root);p=cached_preview(root,month,revision)
    if p['sync_pending']:
        st.warning('A projeção comercial precisa incorporar registros já existentes; os originais não serão reimportados.')
        if st.button('Preparar índices comerciais com backup'):
            with st.status('Criando backup consistente e preparando em lotes…') as status:
                progress=st.empty();n=api.sync(root,lambda n:progress.write(f'{n:,} registros projetados'))
                status.update(label=f'{n} registros preparados',state='complete')
            st.rerun()
    cols=st.columns(3);cols[0].metric('Vistorias · valor aprovado' if p['approved'] else 'Vistorias · prévia',money(p['inspection_cents']));cols[1].metric('Pendências comerciais',p['pending']);cols[2].metric('Geolocalização',money(p['geo']['cents']))
    if p['approved']:st.success('Competência aprovada. Valores preservados por fotografia mensal.')
    else:st.warning('PRÉVIA — não é fechamento definitivo; depende da conciliação e aprovação.')
    st.dataframe(pd.DataFrame(p['services']),hide_index=True)
    st.dataframe(pd.DataFrame(p['groups']),hide_index=True)
    if p['undated']:st.warning(f"{p['undated']} registros fechados sem data de execução: pendências globais, sem competência presumida.")
    if page=='Painel de Vistorias':
        import inspections
        first,last=api.month_bounds(month);total,_,pending=inspections.summary(root,first,last)
        st.metric('Vistorias operacionais com prazo apurável',total['total']);st.metric('Dentro do prazo',f"{total['percent']:.2f}%" if total['percent'] is not None else 'Sem dados')
        st.caption('Quantidade operacional não corresponde necessariamente à quantidade faturável. Atraso não exclui faturamento.')
        return
    st.subheader('Conciliação antes da aprovação')
    st.caption('As referências abaixo são opcionais e só calculam diferenças. Não alteram a classificação nem as quantidades apuradas.')
    references={}
    with st.expander('Informar referências da tabela dinâmica para comparação'):
        for r in p['services']:
            value=st.text_input(f"Referência · {r['name']}",key='ref_'+r['code'])
            if value.strip():
                try:
                    ref=int(value)
                    if ref<0:raise ValueError()
                    references[r['code']]=ref
                except ValueError:st.error('Referência deve ser inteira e não negativa.');return
    comparisons=[{'Código':r['code'],'Serviço':r['name'],'Apurado':r['quantity'],'Referência':references.get(r['code']),'Diferença':r['quantity']-references[r['code']] if r['code'] in references else None} for r in p['services']]
    st.dataframe(pd.DataFrame(comparisons),hide_index=True)
    detailed=st.checkbox('Incluir registros e motivos individuais na conciliação')
    scope=(month,revision,json.dumps(references,sort_keys=True),detailed)
    if st.button('Gerar relatório de conciliação'):
        with st.spinner('Exportando somente os dados solicitados…'):
            st.session_state['inspection_reconciliation']=(scope,api.reconciliation(root,month,references,detailed),p['fingerprint'])
    prepared=st.session_state.get('inspection_reconciliation')
    if prepared and prepared[0]==scope:st.download_button('Baixar conciliação Excel',prepared[1],file_name=f'conciliacao-vistorias-{month}.xlsx',on_click='ignore')
    offset=st.number_input('Página de registros',min_value=1,value=1,step=1)
    st.dataframe(pd.DataFrame(cached_details(root,month,revision,(offset-1)*50)),hide_index=True)
    st.caption('Até 50 registros por página; os valores brutos continuam preservados no banco operacional e nos originais.')
    if page=='Faturamento de Vistorias' and not p['approved']:
        with st.form('approve_inspection'):
            evidence=st.text_input('Documento e responsável pela conciliação')
            confirmed=st.checkbox('Conferi o relatório, as diferenças e o escopo, e confirmo o faturamento e a geolocalização desta competência.')
            submit=st.form_submit_button('Aprovar faturamento mensal',disabled=not p['ready'] or not p['geo']['ready'] or not prepared or prepared[0]!=scope)
        if submit:
            try:api.approve(root,month,prepared[2],evidence,confirmed);st.rerun()
            except ValueError as e:st.error(str(e))
    if st.button('Preparar catálogo para validação independente'):
        st.session_state['inspection_catalog_export']=(month,revision,json.dumps(api.export_catalog(root,month),ensure_ascii=False,indent=2))
    config=st.session_state.get('inspection_catalog_export')
    if config and config[:2]==(month,revision):st.download_button('Baixar catálogo de conferência',config[2],file_name=f'catalogo-vistorias-{month}.json',on_click='ignore')
    with st.expander('Conferir pendência individual (sem alterar dados originais)'):
        with st.form('review_visit'):
            id=st.number_input('ID do registro',min_value=1,step=1)
            decision=st.selectbox('Decisão individual',['Excluir','Cobrar'])
            services=[s for s in api.service_list(root,month) if s['code']!='geo'];codes=[s['code'] for s in services]
            code=st.selectbox('Código contratual',codes)
            evidence=st.text_input('Justificativa/documento da análise individual')
            yes=st.checkbox('Confirmo esta decisão apenas para o registro e competência selecionados')
            if st.form_submit_button('Registrar conferência'):
                if not yes:st.error('Confirmação explícita obrigatória.')
                else:
                    try:api.review(root,id,month,decision,code,evidence);st.rerun()
                    except ValueError as e:st.error(str(e))

def import_panel(root):
    import inspections
    st.info('Fonte inicial confirmada: aba Número OS. A dinâmica e as cópias não entram como novos registros. Importações anteriores não precisam ser repetidas.')
    upload=st.file_uploader('Excel original de Vistorias',type=['xlsx'])
    if upload:
        content=upload.getvalue()
        try:options=workbook_sheets(content)
        except Exception as e:st.error(str(e));return
        if not options:st.error('Nenhuma aba de registros de vistorias válida.');return
        sheet=st.selectbox('Aba original',options,index=options.index('Número OS') if 'Número OS' in options else 0)
        yes=st.checkbox('Confirmo esta aba original. Duplicidades e ligação inativa permanecem para conferência comercial, sem cobrança automática.')
        if st.button('Importar Vistorias',disabled=not yes):
            try:
                with st.status('Importando em lotes…') as status:
                    progress=st.empty();n=inspections.import_file(root,content,upload.name,sheet,lambda n:progress.write(f'{n:,} linhas processadas'))
                    api.sync(root,lambda n:progress.write(f'{n:,} linhas preparadas para consultas comerciais'))
                    status.update(label=f'{n} registros importados e preparados',state='complete')
                st.success('Importação concluída.');st.rerun()
            except Exception as e:st.error(f'Confira a situação da importação: {e}. Se apenas a projeção falhou, use Preparar índices comerciais; não reimporte.')
    with inspections.connect(root) as c:
        rows=[dict(r) for r in c.execute('SELECT i.*,COUNT(v.id) records FROM imports i LEFT JOIN visits v ON v.import_id=i.id GROUP BY i.id ORDER BY i.id DESC LIMIT 50')]
    st.dataframe(pd.DataFrame(rows),hide_index=True)
    if st.button('Atualizar projeção comercial dos registros existentes'):
        with st.spinner('Backup inicial e atualização incremental…'):api.sync(root)
        st.rerun()

def catalog(root,month):
    services=api.service_list(root,month);st.dataframe(pd.DataFrame(services),hide_index=True)
    st.caption('Os códigos 200014104/105/106 são contratuais confirmados. geo é apenas identificador interno; seu código contratual não foi informado. Sem associação aproximada de TSS.')
    selected=st.selectbox('Serviço',['Novo serviço']+[s['code'] for s in services])
    old=next((s for s in services if s['code']==selected),None)
    with st.form('price_service'):
        code=st.text_input('Código contratual confirmado',value=old['code'] if old else '')
        name=st.text_input('Descrição contratual',value=old['name'] if old else '')
        price=st.text_input('Preço unitário em reais',value=f"{old['cents']/100:.2f}".replace('.',',') if old else '')
        effective=st.text_input('Vigência (AAAA-MM)',value=month)
        active=st.checkbox('Serviço ativo',value=bool(old['active']) if old else True)
        evidence=st.text_input('Documento/justificativa do preço')
        if st.form_submit_button('Salvar serviço/preço'):
            try:api.save_service(root,code,name,effective,cents(price),active,evidence);st.rerun()
            except (ValueError,InvalidOperation) as e:st.error(str(e))
    st.subheader('Classificação das descrições originais')
    st.caption('TSS exato após padronização de espaços, caixa e acentos. Causa/formulário em branco abrangem todos os resultados. Regras específicas prevalecem; empate fica pendente.')
    with st.form('map_service'):
        tss=st.text_input('TSS original');cause=st.text_input('Causa Resultado (opcional)');form=st.text_input('Formulário de Baixa (opcional)')
        decision=st.selectbox('Decisão',['Cobrar','Excluir']);code=st.selectbox('Serviço para cobrança',[s['code'] for s in services if s['code']!='geo'])
        effective=st.text_input('Competência inicial da classificação',value=month);evidence=st.text_input('Documento/justificativa da classificação')
        if st.form_submit_button('Salvar classificação'):
            try:api.save_rule(root,tss,cause,form,effective,decision,code,evidence);st.rerun()
            except ValueError as e:st.error(str(e))
    page=st.number_input('Página do catálogo',min_value=1,step=1)
    with api.connect(root) as c:
        rules=[dict(r) for r in c.execute('SELECT * FROM rules ORDER BY tss,effective DESC LIMIT 50 OFFSET ?',((page-1)*50,))]
        history=[dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 50')]
    st.dataframe(pd.DataFrame(rules),hide_index=True)
    with st.expander('Histórico de alterações (50 eventos mais recentes)'):st.dataframe(pd.DataFrame(history),hide_index=True)

def geolocation(root,month):
    with api.connect(root) as c:
        old=c.execute('SELECT * FROM geo WHERE month=?',(month,)).fetchone()
        initial=json.loads(old['cities']) if old else {}
    st.caption('O modo principal define a cobrança; o outro é só conferência. Divergências impedem aprovação. Nenhuma quantidade é cadastrada automaticamente.')
    with st.form('geolocation'):
        mode=st.selectbox('Modo principal',['Total mensal','Por município'],index=0 if not old or old['mode']=='Total mensal' else 1)
        total=st.text_input('Total Sabesp (opcional para conferência por município)',value=str(old['total']) if old and old['total'] is not None else '')
        cities=st.text_area('Municípios: uma linha Município;quantidade',value='\n'.join(f'{k};{v}' for k,v in initial.items()))
        evidence=st.text_input('Documento Sabesp e justificativa da inclusão/edição')
        yes=st.checkbox('Confirmo as quantidades documentadas desta competência')
        if st.form_submit_button('Salvar Geolocalização'):
            try:
                if not yes:raise ValueError('Confirmação obrigatória.')
                parsed={}
                for line in cities.splitlines():
                    if not line.strip():continue
                    town,qty=line.rsplit(';',1);town=town.strip()
                    if town in parsed:raise ValueError('Município repetido.')
                    parsed[town]=int(qty.strip())
                api.save_geo(root,month,mode,int(total) if total.strip() else None,parsed,evidence);st.rerun()
            except ValueError as e:st.error(str(e))
    with api.connect(root) as c:result=api.geo_summary(c,month,api.service_list_connection(c,month))
    st.write(result)
