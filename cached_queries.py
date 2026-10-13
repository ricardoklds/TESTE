import streamlit as st
import queries

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def overview(path,revision,month,start=None,end=None):
    return queries.overview(month,start,end)

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def productivity(path,revision,month,prices,by,start=None,end=None):
    return queries.productivity(month,prices,by,start,end)

@st.cache_data(show_spinner=False,max_entries=128,ttl=600)
def record_page(path,revision,month,start,end,category,mode,offset,limit):
    return queries.record_page(month,start,end,category,mode,offset,limit)

@st.cache_data(show_spinner=False,max_entries=64,ttl=600)
def import_preview(path,revision,month,import_id):
    import storage
    return storage.import_preview(month,import_id)
