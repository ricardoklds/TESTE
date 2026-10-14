import streamlit as st
import queries

@st.cache_data(show_spinner=False,max_entries=64,ttl=600)
def import_listing(path,revision,month,prices):
    return queries.import_listing(month,prices)

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def overview(path,revision,month,start=None,end=None):
    import holidays
    return {**queries.overview(month,start,end),**holidays.overview(month,start,end)}

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def productivity(path,revision,month,prices,by,start=None,end=None):
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
def holiday_page(path,revision,month,start,end,offset,limit,municipality=None,group=None,employee=None):
    import holidays
    return holidays.page(month,start,end,offset,limit,municipality,group,employee)

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def holiday_options(path,revision,month,start,end):
    import holidays
    return holidays.filter_options(month,start,end)

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def record_page(path,revision,month,start,end,category,mode,offset,limit):
    return queries.record_page(month,start,end,category,mode,offset,limit)

@st.cache_data(show_spinner=False,max_entries=64,ttl=600)
def import_preview(path,revision,month,import_id):
    import storage
    return storage.import_preview(month,import_id)
