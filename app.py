from datetime import date
import streamlit as st
from pathlib import Path
import os

st.set_page_config(page_title='Gestão de Medição | Fechamento',page_icon='💧',layout='wide')
st.markdown('''<style>
.block-container{padding-top:2rem;max-width:1450px} h1{font-weight:750;letter-spacing:-1px}
[data-testid="stSidebar"]{background:#163a60} [data-testid="stSidebar"] *{color:#f7fafc}
[data-testid="stMetric"]{background:white;border:1px solid #dce5ee;border-radius:12px;padding:18px}
.stButton button{border-radius:8px} [data-testid="stSidebar"] input{color:#163a60}
</style>''',unsafe_allow_html=True)

@st.cache_data(show_spinner=False,max_entries=8)
def parsed_file(content):
    import excel_io
    return excel_io.inspect(content)

with st.sidebar:
    st.title('💧 Medição')
    st.caption('GESTÃO DO CONTRATO')
    import navigation
    module,page=navigation.sidebar(st)
    st.divider()
    reference=st.date_input('Mês de referência',value=date(2026,10,1),format='DD/MM/YYYY')
    month=reference.strftime('%Y-%m')
    st.caption('O dia selecionado não afeta o fechamento.')
    st.caption('Dados locais · Originais preservados')

data_path=Path(os.environ.get('APP_DATA_DIR',str(Path(__file__).parent/'data')))
if module=='Vistorias':
    import inspection_module_ui
    inspection_module_ui.render(data_path,month,page)
    st.stop()
if module in ('Painel geral','Fechamento geral'):
    import contract_ui
    contract_ui.render(data_path,month,allow_close=module=='Fechamento geral')
    st.stop()

import readings_ui
readings_ui.render(month,page,parsed_file,reference)
