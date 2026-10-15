import sys,tempfile,time,json,sqlite3,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import inspections as api
result={}
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--excel',type=Path);parser.add_argument('--output',type=Path,default=Path('measurements/inspection-deadlines/results.json'));args=parser.parse_args()
if args.excel:
 with tempfile.TemporaryDirectory() as root:
  p=args.excel
  t=time.perf_counter();n=api.import_file(root,p.read_bytes(),p.name,'Número OS');result['real_excel_import_seconds']=time.perf_counter()-t
  total,rows,pending=api.summary(root,'2026-09-01','2026-09-30');result['real_excel']={'count':n,'total':total,'municipalities':len(rows),'pending':pending}
with tempfile.TemporaryDirectory() as root:
 c=api.connect(root);t=time.perf_counter()
 for start in range(0,500000,5000):
  c.executemany('INSERT INTO visits(import_id,line,os,city,day,status,fingerprint,raw) VALUES(?,?,?,?,?,?,?,?)',[(1,i,str(i),'Município '+str(i%100),'2026-09-'+str(1+i%30).zfill(2),'Fora do prazo' if i%100==0 else 'Dentro do prazo',str(i),'{}') for i in range(start,start+5000)])
 c.commit();c.close();result['synthetic_insert_seconds']=time.perf_counter()-t
 times=[]
 for _ in range(3):
  t=time.perf_counter();total,rows,pending=api.summary(root,'2026-09-01','2026-09-30');times.append(time.perf_counter()-t)
 result['synthetic_500k']={'summary_seconds':times,'total':total,'municipalities':len(rows)}
 t=time.perf_counter();b=api.export(root,'2026-09-01','2026-09-30',True);result['synthetic_detail_export']={'seconds':time.perf_counter()-t,'bytes':len(b),'late_records':5000}
with tempfile.TemporaryDirectory() as root:
 os.environ['APP_DATA_DIR']=root
 from streamlit.testing.v1 import AppTest
 a=AppTest.from_file(str(Path(__file__).resolve().parent/'app.py'),default_timeout=30).run()
 a.sidebar.selectbox[0].set_value('Vistorias').run()
 a.sidebar.radio[0].set_value('Prazos e Meta Contratual').run()
 assert not a.exception,repr(a.exception)
 assert any('Meta contratual'==e.value for e in a.subheader)
 result['ui_empty']='AppTest: Vistorias abre, sem exceção, card e controles presentes'
print(json.dumps(result,ensure_ascii=False,indent=2));args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2))
