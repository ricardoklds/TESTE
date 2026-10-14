import streamlit as st
import queries

@st.cache_data(show_spinner=False,max_entries=64,ttl=600)
def import_listing(path,revision,month,prices):
    """Política municipal Bocaina/SP, revisão de código 2026-10-14."""
    return queries.import_listing(month,prices)

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def overview(path,revision,month,start=None,end=None):
    """Política municipal Bocaina/SP, revisão de código 2026-10-14."""
    import holidays
    return {**queries.overview(month,start,end),**holidays.overview(month,start,end)}

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def productivity(path,revision,month,prices,by,start=None,end=None):
    """Política municipal Bocaina/SP, revisão de código 2026-10-14."""
    import holidays
    result=queries.productivity(month,prices,by,start,end)
    extras=holidays.productivity(month,by,start,end)
    for row in result:
        quantity=extras.pop(next(iter(row.values())),0)
        total=row.pop('total_cents');row['Feriados']=quantity;row['total_cents']=total+quantity*105
    label={'employee':'Funcionário','city':'Unidade / cidade (ATC)','group':'Grupo'}[by]
    for name,quantity in extras.items():
        result.append({label:name,'Registros':0,'Leituras faturáveis':0,'Comunicados':0,'Apontamentos':0,'Feriados':quantity,'total_cents':quantity*105})
    return result

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def holiday_page(path,revision,month,start,end,offset,limit,municipality=None,group=None,employee=None,situation='Todos'):
    """Política municipal Bocaina/SP, revisão de código 2026-10-14."""
    import holiday_review
    if situation not in holiday_review.SITUATIONS:raise ValueError('Situação inválida.')
    groups=holiday_review_statistics(path,revision,month,start,end,municipality,group,employee)
    count=sum(r['n'] for r in groups if situation=='Todos' or
              situation=='Elegíveis cobrados' and r['charged'] or
              situation=='Pendências' and r['pending'] or situation=='Não cobrados' and not r['charged'])
    return holiday_review.page(month,start,end,offset,limit,municipality,group,employee,situation,known_count=count)

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def holiday_review_statistics(path,revision,month,start,end,municipality=None,group=None,employee=None):
    """Política municipal Bocaina/SP, revisão de código 2026-10-14."""
    import holiday_review
    return holiday_review.statistics(month,start,end,municipality,group,employee)

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def holiday_pending_summary(path,revision,month,start,end,municipality=None,group=None,employee=None):
    """Política municipal Bocaina/SP, revisão de código 2026-10-14."""
    return [{'Motivo':r['reason'],'Quantidade':r['n']} for r in
            holiday_review_statistics(path,revision,month,start,end,municipality,group,employee) if r['pending']]

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def holiday_options(path,revision,month,start,end):
    """Política municipal Bocaina/SP, revisão de código 2026-10-14."""
    import holidays
    return holidays.filter_options(month,start,end)

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def record_page(path,revision,month,start,end,category,mode,offset,limit):
    return queries.record_page(month,start,end,category,mode,offset,limit)

@st.cache_data(show_spinner=False,max_entries=64,ttl=600)
def import_preview(path,revision,month,import_id):
    """Política municipal Bocaina/SP, revisão de código 2026-10-14."""
    import storage
    return storage.import_preview(month,import_id)
