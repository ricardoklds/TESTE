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
def cached_municipal(root,month,revision):return api.municipal_summary(root,month)
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

def service_frame(rows):
    if not any('quantity' in r for r in rows):
        return pd.DataFrame([{'Código':r['code'],'Serviço':r['name'],'Valor unitário':money(r['cents']),'Vigência':r.get('effective','—'),'Situação':'Ativo' if r.get('active',1) else 'Inativo'} for r in rows])
    return pd.DataFrame([{'Código':r['code'],'Serviço':r['name'],'Quantidade':r['quantity'],'Valor unitário':money(r['unit_cents']) if r.get('unit_cents') is not None else 'Valores variados','Valor total':money(r['cents'])} for r in rows])

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
    with st.expander('Quantidades por valor unitário efetivo'):st.dataframe(pd.DataFrame(p.get('rates',[])),hide_index=True)
    st.dataframe(pd.DataFrame(p['groups']),hide_index=True)
    with st.expander('Produção e faturamento contratual por município'):
        st.dataframe(pd.DataFrame(p['municipalities'] if 'municipalities' in p else cached_municipal(root,month,revision)),hide_index=True)
        st.caption('Sem atribuição de funcionário: o Excel de Vistorias não informa o executor individual.')
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
        st.session_state['inspection_catalog_export']=(month,revision,json.dumps(api.export_period_catalog(root,month),ensure_ascii=False,indent=2))
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
        yes=st.checkbox('Confirmo esta aba original. Escopo e critérios comerciais vigentes serão aplicados; serviços desconhecidos permanecem pendentes.')
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

@st.cache_data(show_spinner=False,max_entries=16)
def cached_catalog(root,revision):return api.catalog_state(root)

def catalog(root,month,rules_only=False):
    services=api.service_list(root,month)
    state=cached_catalog(root,api.revision(root))
    if not rules_only:
        st.dataframe(service_frame(services),hide_index=True)
        st.caption('Preços de categoria e preços específicos por TSS são distintos. Alterar o preço da categoria afeta todas as descrições que a seguem; preço específico afeta somente o TSS. Não altera Leituras.')
        st.info('Correção confirmada: VERIFICAR SERVIÇO EXECUTADO pertence a Predial (200014106, R$ 22,50). Em instalações anteriores, selecione esse TSS, escolha Predial com vigência 2026-09, confira o impacto e confirme. Meses aprovados permanecem bloqueados.')
        selected=st.selectbox('Serviço',['Novo serviço']+[s['code'] for s in services],format_func=lambda code:next((s['name']+' · '+code for s in services if s['code']==code),code))
        old=next((s for s in services if s['code']==selected),None)
        with st.form('price_service'):
            code=st.text_input('Código contratual confirmado',value=old['code'] if old else '')
            name=st.text_input('Descrição contratual',value=old['name'] if old else '')
            price=st.text_input('Preço unitário em reais',value=f"{old['cents']/100:.2f}".replace('.',',') if old else '')
            effective=st.text_input('Vigência (AAAA-MM)',value=month)
            active=st.checkbox('Serviço ativo',value=bool(old['active']) if old else True)
            evidence=st.text_input('Documento/justificativa do preço')
            if st.form_submit_button('Calcular impacto do serviço/preço'):
                try:
                    change={'kind':'service','code':code,'name':name,'effective':effective,'cents':cents(price),'active':active,'evidence':evidence}
                    with st.spinner('Simulando em transação reversível…'):st.session_state['catalog_plan']=api.prepare_change(root,change)
                except (ValueError,InvalidOperation) as e:st.error(str(e))
        st.subheader('Classificação das descrições originais')
        options=sorted({r['tss'] for r in state['rules']})
        choice=st.selectbox('Descrição TSS para editar',['Nova descrição']+options)
        candidates=[r for r in state['rules'] if r['tss']==choice and r['effective']<=month and not r['cause'] and not r['form']]
        current=max(candidates,key=lambda r:(r['effective'],r['id'])) if candidates else None
        codes=[s['code'] for s in services if s['code']!='geo'];names={s['code']:s['name'] for s in services}
        situation={'Cobrar':'Faturável','Excluir':'Não faturável','Pendente':'Pendente'}
        with st.form('map_service'):
            tss=st.text_input('TSS original',value='' if choice=='Nova descrição' else choice)
            cause=st.text_input('Causa Resultado (opcional)');form=st.text_input('Formulário de Baixa (opcional)')
            decision=st.selectbox('Situação comercial',list(situation),index=list(situation).index(current['decision']) if current else 2,format_func=lambda v:situation[v])
            code=st.selectbox('Categoria para cobrança',codes,index=codes.index(current['code']) if current and current['code'] in codes else 0,format_func=lambda k:names[k]+' · '+k)
            custom=[o for o in state['tss_prices'] if o['tss']==choice and o['effective']<=month]
            rate=max(custom,key=lambda o:o['effective'])['cents'] if custom else None
            unit=st.text_input('Preço específico deste TSS (R$; vazio segue a categoria)',value=f'{rate/100:.2f}'.replace('.',',') if rate is not None else '')
            st.caption('Ex.: categoria Predial e preço específico 12,00 altera só esta descrição. Deixar vazio volta a seguir a tarifa da categoria. Preços específicos abrangem o TSS inteiro, não apenas a causa/formulário.')
            effective=st.text_input('Competência inicial da classificação',value=month);evidence=st.text_input('Documento/justificativa da classificação')
            if st.form_submit_button('Calcular impacto da classificação'):
                try:
                    change={'kind':'rule','tss':tss,'cause':cause,'form':form,'effective':effective,'decision':decision,'code':code,'unit_cents':cents(unit) if unit.strip() else None,'evidence':evidence}
                    with st.spinner('Calculando impacto das competências abertas…'):st.session_state['catalog_plan']=api.prepare_change(root,change)
                except (ValueError,InvalidOperation) as e:st.error(str(e))
    if rules_only:
        import inspection_contract
        policy=inspection_contract.from_root(root,month)
        st.subheader('Critério de faturamento por categoria')
        st.caption('Aprovação: uma cobrança por OS, representada pela última execução elegível. Empates pelo menor ID original. Outras categorias continuam em conferência manual de repetições até mudança explícita.')
        mode_code=st.selectbox('Categoria do critério',[s['code'] for s in services if s['code']!='geo'],format_func=lambda code:next(s['name'] for s in services if s['code']==code))
        with st.form('billing_mode'):
            mode=st.selectbox('Critério de cobrança',list(inspection_contract.LABELS),index=list(inspection_contract.LABELS).index(policy['modes'].get(mode_code,'manual')),format_func=lambda v:inspection_contract.LABELS[v])
            effective=st.text_input('Vigência do critério',value=month)
            evidence=st.text_input('Justificativa/documento do critério')
            if st.form_submit_button('Calcular impacto do critério'):
                try:
                    with st.spinner('Simulando critérios e competências abertas…'):st.session_state['catalog_plan']=api.prepare_change(root,{'kind':'billing_mode','code':mode_code,'mode':mode,'effective':effective,'evidence':evidence})
                except ValueError as e:st.error(str(e))
    plan=st.session_state.get('catalog_plan')
    if plan and plan['root']==str(Path(root).resolve()) and (plan['change']['kind']=='billing_mode')==rules_only:
        st.subheader('Prévia de impacto — nada foi salvo')
        st.write(plan['change'])
        st.dataframe(pd.DataFrame([{'Competência':r['month'],'Vistorias antes':money(r['before']['inspection_cents']),'Vistorias depois':money(r['after']['inspection_cents']),'Geolocalização antes':money(r['before']['geo_cents']),'Geolocalização depois':money(r['after']['geo_cents']),'Variação':money(r['delta_cents']),'Pendências antes':r['before']['pending'],'Pendências depois':r['after']['pending']} for r in plan['impact']]),hide_index=True)
        with st.expander('Quantidades e valores por categoria antes/depois'):
            for r in plan['impact']:
                st.write(r['month']);st.dataframe(service_frame(r['before']['services']),hide_index=True);st.dataframe(service_frame(r['after']['services']),hide_index=True)
        with st.form('confirm_catalog_change'):
            yes=st.checkbox('Conferi a vigência e o impacto acima e confirmo esta alteração do catálogo')
            submit=st.form_submit_button('Confirmar alteração após impacto')
        if submit:
            try:api.confirm_change(root,plan,yes);st.session_state.pop('catalog_plan',None);st.rerun()
            except ValueError as e:st.error(str(e))
        if st.button('Cancelar alteração'):st.session_state.pop('catalog_plan',None);st.rerun()
    page=st.number_input('Página do catálogo',min_value=1,step=1)
    history_page=st.number_input('Página do histórico',min_value=1,step=1)
    with api.connect(root) as c:
        rules=[dict(r) for r in c.execute('SELECT * FROM rules ORDER BY tss,effective DESC LIMIT 50 OFFSET ?',((page-1)*50,))]
        history=[dict(r) for r in c.execute('SELECT * FROM audit ORDER BY id DESC LIMIT 50 OFFSET ?',((history_page-1)*50,))]
    if not rules_only:
        st.dataframe(pd.DataFrame(rules).rename(columns={'tss':'Descrição TSS','cause':'Causa','form':'Formulário','effective':'Vigência','code':'Código','decision':'Situação','evidence':'Justificativa'}),hide_index=True)
        st.dataframe(pd.DataFrame([{'Descrição TSS':r['tss'],'Vigência':r['effective'],'Valor unitário':money(r['cents']) if r['cents'] is not None else 'Segue a categoria'} for r in state['tss_prices']]),hide_index=True)
    with st.expander('Histórico de alterações (50 eventos por página)'):st.dataframe(pd.DataFrame(history).rename(columns={'id':'Registro','created':'Data e hora (UTC)','action':'Ação','payload':'Detalhes'}),hide_index=True)


def geolocation(root,month):
    import inspection_contract
    with api.connect(root) as c:
        row=c.execute('SELECT * FROM geo WHERE month=?',(month,)).fetchone()
        old=dict(row) if row else None
        price=api.service_list_connection(c,month).get('geo')
        policy=inspection_contract.policy(c,month)
        approved=c.execute('SELECT 1 FROM approvals WHERE month=?',(month,)).fetchone() is not None
    initial=json.loads(old['cities']) if old else {}
    st.text_input('Competência',value=month,disabled=True)
    with st.expander('Detalhar por município (opcional)',expanded=bool(old and old['mode']=='Por município')):
        mode=st.radio('Forma de lançamento',['Total mensal','Por município'],index=1 if old and old['mode']=='Por município' else 0,key='geo_mode:'+root+month,disabled=approved)
        cities_text=st.text_area('Municípios e quantidades (Município;quantidade)',value='\n'.join(f'{k};{v}' for k,v in initial.items()),key='geo_cities:'+root+month,disabled=approved or mode=='Total mensal')
    parsed={};error=None
    if mode=='Por município':
        try:
            for line in cities_text.splitlines():
                if not line.strip():continue
                if ';' not in line:raise ValueError('Use uma linha Município;quantidade.')
                town,text=line.rsplit(';',1);town=town.strip()
                try:value=int(text.strip())
                except ValueError:raise ValueError('A quantidade deve ser um número inteiro não negativo.')
                if not town or value<0:raise ValueError('Informe município e quantidade inteira não negativa.')
                if api.norm(town) in {api.norm(k) for k in parsed}:raise ValueError('Município repetido.')
                parsed[town]=value
            if not parsed:raise ValueError('Informe pelo menos um município e sua quantidade.')
        except ValueError as e:error=str(e)
    initial_total=old['total'] if old and old['mode']=='Total mensal' else None
    if mode=='Total mensal':
        total=st.number_input('Quantidade',min_value=0,value=initial_total,step=1,placeholder='Informe a quantidade',key='geo_quantity:'+root+month,disabled=approved)
    else:total=None
    preview_total=(total if total is not None else 0) if mode=='Total mensal' else None
    result=api.geo_values({'mode':mode,'total':preview_total,'cities':parsed},policy,price)
    if mode=='Por município':st.metric('Quantidade contratual','—' if error else result['quantity'])
    cols=st.columns(2);cols[0].metric('Preço unitário vigente',money(price['cents']) if price else 'Não cadastrado')
    cols[1].metric('Valor total',money(result['cents']) if (mode=='Por município' and not error) or total is not None else '—')
    if approved:st.info('Competência aprovada: lançamento e valores preservados.')
    if error:st.error(error)
    if result.get('out_of_scope_quantity'):st.info(f"{result['out_of_scope_quantity']} geolocalizações fora do contrato: preservadas, sem cobrança.")
    if result.get('unknown_municipalities'):st.warning('Município não autorizado: lançamento permanece pendente para conferência, sem aprovação automática.')
    if price and not price['active']:st.warning('Preço inativo: revise Serviços e Preços de Vistorias.')
    if st.button('Salvar',disabled=approved or error is not None or (mode=='Total mensal' and total is None)):
        try:
            # Salvar substitui somente o lançamento do mês; audit guarda o anterior.
            # Os dois modos nunca são somados.
            api.save_geo(root,month,mode,total,parsed if mode=='Por município' else {})
            st.success('Quantidade salva.');st.rerun()
        except ValueError as e:st.error(str(e))
