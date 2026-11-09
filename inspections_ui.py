"""Tela operacional independente de leituras e de cálculo de preços de vistorias."""
import calendar
from datetime import date
from decimal import Decimal,InvalidOperation
from pathlib import Path
import pandas as pd
import streamlit as st
import inspections as api

@st.cache_data(show_spinner=False,max_entries=32)
def cached_summary(root,version,start,end):return api.summary(root,start,end)

def render(data,month,show_import=True,show_fine=True):
    root=str(Path(data)/'vistorias');st.title('Vistorias · prazo contratual')
    st.caption('Indicador operacional independente do faturamento. Nenhum desconto é aplicado ao fechamento oficial.')
    if show_import:
        with st.expander('Importar base de vistorias'):
            upload=st.file_uploader('Excel original de vistorias',type=['xlsx'],key='inspection_upload')
            if upload:
                content=upload.getvalue()
                try:choices=api.sheets(content)
                except Exception as e:st.error(str(e));return
                if not choices:st.error('Nenhuma aba com os cabeçalhos obrigatórios.');return
                sheet=st.selectbox('Aba de registros originais',choices)
                st.warning('Não some abas copiadas. OS repetidas com datas/resultados distintos são mantidas como ocorrências para conferência, não como cobrança.')
                if st.button('Importar vistorias'):
                    progress=st.empty()
                    try:
                        count=api.import_file(root,content,upload.name,sheet,lambda n:progress.write(f'{n:,} registros processados; aguardando confirmação da transação.'))
                        st.success(f'{count} registros importados.');st.session_state.pop('inspection_export',None)
                    except Exception as e:st.error(f'Importação cancelada integralmente: {e}')
    first=date.fromisoformat(month+'-01');last=first.replace(day=calendar.monthrange(first.year,first.month)[1])
    mode=st.radio('Período das vistorias',['Mês completo','Dia específico','Intervalo personalizado'],horizontal=True)
    start,end=first,last
    if mode=='Dia específico':start=end=st.date_input('Data da execução',first,min_value=first,max_value=last)
    elif mode=='Intervalo personalizado':
        start=st.date_input('Execução inicial',first,min_value=first,max_value=last);end=st.date_input('Execução final',last,min_value=first,max_value=last)
    if end<start:st.error('Intervalo inválido.');return
    start,end=start.isoformat(),end.isoformat()
    with api.connect(root) as c:
        version=tuple(c.execute('SELECT COUNT(*),COALESCE(MAX(id),0) FROM imports').fetchone())
    import inspection_contract
    scope_policy=inspection_contract.from_root(root,month)
    total,rows,pending=cached_summary(root,(version,str(scope_policy)),start,end)
    scope=(version,start,end,str(scope_policy))
    with st.container(border=True):
        st.subheader('Meta contratual');st.metric('Meta de vistorias dentro do prazo','99%')
        if total['total']:
            st.progress(total['percent']/100,text=f"Resultado real: {total['percent']:.2f}% · referência contratual: 99%")
            st.write('⚠ Apuração incompleta' if pending else ('✓ Meta atingida' if total['met'] else '⚠ Meta não atingida — possibilidade de glosa'))
        else:st.info('Sem vistorias com prazo apurável no período.')
        st.caption('No mínimo 99% das vistorias concluídas devem estar dentro do prazo para evitar glosa contratual. O limite é inclusivo: execução até o prazo final está dentro do prazo.')
    cols=st.columns(5)
    for col,label,val in zip(cols,['Vistorias com prazo apurável','Dentro do prazo','Fora do prazo','% dentro do prazo','% fora do prazo'],[total['total'],total['inside'],total['outside'],f"{total['percent']:.2f}%" if total['percent'] is not None else '—',f"{total['outside_percent']:.2f}%" if total['outside_percent'] is not None else '—']):col.metric(label,val)
    if pending:st.warning(f'{pending} registros fechados pendentes de data/prazo ou município autorizado. Os sem data de execução não podem ser atribuídos a este período; são informados globalmente. A meta é provisória e o cálculo de multa permanece bloqueado.')
    if total.get('out_of_scope'):st.info(f"{total['out_of_scope']} registros fora do escopo do contrato: preservados na auditoria, fora dos indicadores contratuais.")
    st.caption('Escopo municipal exclusivo de Vistorias. Quantidade operacional conta ocorrências, não OS faturáveis. Base: OS Fechada e Operação Fechada, independentemente de aprovação, recusa ou glosa. Período pela Data Fim Execução. Tempo Residual é referência de conferência, não substitui as datas.')
    frame=pd.DataFrame([{'Município':r['city'],'Vistorias válidas':r['total'],'Dentro do prazo':r['inside'],'Fora do prazo':r['outside'],'% fora':r['outside_percent'],'Meta contratual (barra)':r['percent'],'Situação':'Apuração incompleta' if pending else ('Meta atingida' if r['met'] else 'Meta não atingida')} for r in rows])
    st.dataframe(frame,hide_index=True,column_config={'Meta contratual (barra)':st.column_config.ProgressColumn('% dentro · meta 99%',min_value=0,max_value=100,format='%.2f%%')})
    if show_fine:
        with st.expander('Histórico auditável de cálculos de multa'):
            with api.connect(root) as c:events=[dict(r) for r in c.execute('SELECT id,created,payload FROM penalties ORDER BY id DESC LIMIT 50')]
            st.dataframe(pd.DataFrame(events),hide_index=True)
        st.caption('A simulação de 1% está disponível no Fechamento Geral e não altera valores oficiais.')
    detail=st.checkbox('Incluir detalhamento das vistorias fora do prazo')
    if st.button('Preparar exportação Excel'):
        with st.spinner('Gerando exportação sob demanda…'):st.session_state['inspection_export']=(scope,detail,api.export(root,start,end,detail))
    prepared=st.session_state.get('inspection_export')
    if prepared and prepared[:2]==(scope,detail):st.download_button('Baixar conferência de prazo',prepared[2],file_name=f'prazo-vistorias-{month}.xlsx',on_click='ignore')
