import hashlib,json,os,sqlite3,tempfile,unittest
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
import openpyxl
import inspections as op
import inspection_billing as b
import inspection_contract as scope
import validar_vistorias as independent

APPROVAL='VISTORIA DE NOVA LIGAÇÃO DE ÁGUA'
class ContractRules(unittest.TestCase):
 def setUp(self):self.temp=tempfile.TemporaryDirectory();self.data=Path(self.temp.name);self.root=self.data/'vistorias';self.files=[]
 def tearDown(self):self.temp.cleanup()
 def load(self,rows=None):
  rows=rows or [{}]
  w=openpyxl.Workbook();s=w.active;s.title='Número OS';s.append([*op.HEADERS,'Contrato'])
  for r in rows:
   d={'os':'1','city':'BOCAINA','status':'Fechada','operation':'Fechada','end':'01/09/2026 12:00','stamp':'01/09/2026 11:00','tss':APPROVAL,'contract':'C1',**r}
   s.append([d['os'],d['city'],d['status'],d['operation'],'01/09/2026 00:00',d['end'],d['stamp'],d['tss'],d['contract']])
  out=BytesIO();w.save(out);f=self.data/f'original-{len(self.files)}.xlsx';f.write_bytes(out.getvalue());self.files.append(f)
  op.import_file(self.root,out.getvalue(),f.name,'Número OS');b.sync(self.root)
 def preview(self,month='2026-09'):return b.preview(self.root,month)
 def records(self,month='2026-09'):return b.detail_page(self.root,month)
 def change(self,**kwargs):
  d={'kind':'billing_mode','code':'200014105','mode':'execution','effective':'2026-09','evidence':'Decisão comercial de teste',**kwargs}
  p=b.prepare_change(self.root,d);b.confirm_change(self.root,p,True);return p
 def compare(self,month='2026-09'):
  result=independent.run(self.files,month,self.data/('check-'+month),b.export_period_catalog(self.root,month),progress=lambda _:None)
  p=self.preview(month);self.assertEqual(result['total_cents'],p['inspection_cents'])
  for service in p['services']:self.assertEqual(result['quantities'].get(service['code'],0),service['quantity'])
  return result
 def test_latest_not_last_row_and_ties(self):
  self.load([{'stamp':'02/09/2026 06:48'},{'stamp':'02/09/2026 06:47'},{'os':'2','stamp':'02/09/2026 10:00'},{'os':'2','stamp':'02/09/2026 10:00','end':'02/09/2026 11:00'}])
  rows=self.records();self.assertEqual([r['id'] for r in rows if r['reason']=='Faturável'],[1,3]);self.assertEqual(self.preview()['inspection_cents'],4500)
  result=self.compare();self.assertEqual([r['line'] for r in result['representatives']],[2,4])
 def test_latest_ineligible_is_never_representative(self):
  self.load([{}, {'stamp':'02/09/2026 10:00','status':'Aberta'},{'stamp':'03/09/2026 10:00','city':'MACATUBA'},{'stamp':'04/09/2026 10:00','tss':'DESCONHECIDO'}])
  self.assertEqual(self.records()[0]['reason'],'Faturável');self.assertEqual(self.preview()['inspection_cents'],2250);self.compare()
 def test_unknown_and_divergent_municipalities_remain_pending(self):
  self.load([{}, {'stamp':'02/09/2026 10:00','city':'AGUDOS'},{'os':'2','city':'MUNICÍPIO NÃO CONFIRMADO'}])
  self.assertEqual(self.preview()['pending'],3);self.assertEqual(self.preview()['inspection_cents'],0);self.compare()
 def test_scope_permanent_all_indicators_and_not_deleted(self):
  self.load([{'city':'Araçoiaba da Serra'},{'os':'2','city':'MACATUBA'},{'os':'3','city':'Bocáina'},{'os':'4','city':'MUNICIPIO NOVO'},{'os':'5','city':'MACATUBA','stamp':'02/10/2026 10:00'}])
  p=self.preview();self.assertEqual(p['inspection_cents'],2250);self.assertEqual(p['pending'],1)
  total,rows,pending=op.summary(self.root,'2026-09-01','2026-09-30');self.assertEqual(total['total'],1);self.assertEqual(total['out_of_scope'],2);self.assertEqual(pending,1)
  self.assertEqual(self.preview('2026-10')['inspection_cents'],0);self.assertEqual(op.summary(self.root,'2026-10-01','2026-10-31')[0]['total'],0)
  with op.connect(self.root) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM visits').fetchone()[0],5)
  self.assertNotIn('MACATUBA',[r['municipality'] for r in b.municipal_summary(self.root,'2026-09')]);self.compare()
 def test_unknown_tss_and_explicit_nonbill_stay_out(self):
  self.load([{'tss':'DESCONHECIDO'},{'os':'2','tss':'VERIFICAR USO DE FONTE ALTERNATIVA'},{'os':'3','tss':'VERIFICAR SERVIÇO EXECUTADO'}])
  p=self.preview();self.assertEqual(p['inspection_cents'],2250);self.assertEqual(p['pending'],1);self.compare()
 def test_other_categories_keep_manual_review(self):
  self.load([{'tss':'VISTORIA CADASTRAL'},{'tss':'VISTORIA CADASTRAL','stamp':'02/09/2026 10:00'}])
  self.assertEqual(self.preview()['pending'],2);self.assertEqual(self.preview()['inspection_cents'],0)
  self.change(code='200014104',mode='execution');self.assertEqual(self.preview()['inspection_cents'],2400);self.compare()
 def test_configurable_modes_and_preview_is_exact_and_readonly(self):
  self.load([{}, {'stamp':'02/09/2026 10:00'}]);bank=self.root/'financeiro.sqlite3';sha=hashlib.sha256(bank.read_bytes()).hexdigest()
  change={'kind':'billing_mode','code':'200014105','mode':'manual','effective':'2026-09','evidence':'Teste'}
  plan=b.prepare_change(self.root,change);self.assertEqual(hashlib.sha256(bank.read_bytes()).hexdigest(),sha);self.assertEqual(plan['impact'][0]['delta_cents'],-2250)
  with self.assertRaises(ValueError):b.confirm_change(self.root,plan,False)
  b.confirm_change(self.root,plan,True);self.assertEqual(self.preview()['pending'],2)
  self.change(mode='execution');self.assertEqual(self.preview()['inspection_cents'],4500)
  self.change(mode='once');self.assertEqual(self.preview()['inspection_cents'],2250)
 def test_same_execution_not_automatically_charged_twice(self):
  self.load([{}, {'end':'01/09/2026 13:00'}]);self.change();self.assertEqual(self.preview()['pending'],2);self.compare()
 def test_once_across_competencies_and_contracts(self):
  self.load([{}, {'stamp':'02/10/2026 10:00'},{'contract':'C2'}])
  self.assertEqual(self.preview()['inspection_cents'],2250);self.assertEqual(self.preview('2026-10')['inspection_cents'],2250)
  self.assertEqual(self.records()[0]['reason'],'Sem cobrança adicional — OS já representada');self.compare();self.compare('2026-10')
 def test_approved_charge_never_moves_or_recharges(self):
  self.load([{}]);b.save_geo(self.root,'2026-09','Total mensal',0,{},'Doc')
  p=self.preview();b.approve(self.root,'2026-09',p['fingerprint'],'Conciliação',True);snapshot=b.financial(self.root,'2026-09');deadline=op.summary(self.root,'2026-09-01','2026-09-30')
  self.load([{'stamp':'02/10/2026 10:00'}]);self.assertEqual(self.preview('2026-10')['pending'],1);self.assertEqual(self.preview('2026-10')['inspection_cents'],0)
  self.assertEqual(b.financial(self.root,'2026-09'),snapshot);self.assertEqual(op.summary(self.root,'2026-09-01','2026-09-30'),deadline);self.assertEqual(self.records()[0]['reason'],'Faturável');self.compare('2026-10')
  for kind in ['scope','billing_mode']:
   with self.assertRaises(ValueError):b.prepare_change(self.root,{'kind':kind,'effective':'2026-09','evidence':'Retroativo'})
 def test_scope_effectivity_impact_history_overlap_and_approval(self):
  self.load([{}, {'os':'2','city':'MACATUBA'},{'os':'3','stamp':'01/10/2026 10:00','city':'MACATUBA'}])
  p=self.change(kind='scope',allowed=scope.ALLOWED+['MACATUBA'],excluded=['ARACOIABA DA SERRA'],effective='2026-10')
  self.assertEqual(p['impact'][0]['delta_cents'],2250);self.assertEqual(p['impact'][0]['after']['deadline']['total'],1)
  self.assertEqual(self.preview()['inspection_cents'],2250);self.assertEqual(self.preview('2026-10')['inspection_cents'],2250)
  with self.assertRaises(ValueError):self.change(kind='scope',allowed=['BOCAINA'],excluded=['BOCAÍNA'])
  with b.connect(self.root) as c:self.assertEqual(c.execute("SELECT COUNT(*) FROM audit WHERE json_extract(payload,'$.change.kind')='scope'").fetchone()[0],1)
 def test_cross_period_impact_is_shown_when_new_eligibility_moves_representative(self):
  self.load([{}, {'stamp':'01/10/2026 10:00'}])
  self.change(kind='scope',allowed=[v for v in scope.ALLOWED if v!='BOCAINA'],excluded=scope.EXCLUDED+['BOCAINA'],effective='2026-10')
  p=self.change(kind='scope',allowed=scope.ALLOWED,excluded=scope.EXCLUDED,effective='2026-10')
  self.assertEqual([(r['month'],r['delta_cents']) for r in p['impact']],[('2026-09',-2250),('2026-10',2250)])
 def test_contract_scope_settings_ui(self):
  from streamlit.testing.v1 import AppTest
  import storage
  self.load()
  with patch.dict(os.environ,{'APP_DATA_DIR':str(self.data)}),patch.object(storage,'DATA',self.data):
   a=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run();a.sidebar.selectbox[0].set_value('Configurações').run();a.sidebar.radio[0].set_value('Municípios do Contrato').run();self.assertFalse(a.exception)
   next(t for t in a.text_input if t.label=='Início de vigência (AAAA-MM)').set_value('2026-10');next(t for t in a.text_input if t.label=='Documento e justificativa do escopo').set_value('Documento teste')
   next(t for t in a.button if t.label=='Calcular impacto do escopo').click().run();self.assertFalse(a.exception)
   next(t for t in a.checkbox if t.label.startswith('Confirmo os municípios')).check();next(t for t in a.button if t.label=='Confirmar escopo').click().run();self.assertFalse(a.exception)

 def test_geo_scope_and_unknown_do_not_enter_contract(self):
  self.load();b.save_geo(self.root,'2026-09','Por município',2,{'BOCAINA':2,'MACATUBA':10},'Documento')
  p=self.preview();self.assertEqual(p['geo']['cents'],2400);self.assertEqual(p['geo']['out_of_scope_quantity'],10);self.assertTrue(p['geo']['ready'])
  b.save_geo(self.root,'2026-09','Por município',2,{'BOCAINA':2,'CIDADE NÃO CONFIRMADA':1},'Documento');self.assertFalse(self.preview()['geo']['ready'])
 def test_mode_editor_requires_explicit_impact_confirmation(self):
  from datetime import date
  from streamlit.testing.v1 import AppTest
  import storage
  self.load([{}, {'stamp':'02/09/2026 10:00'}])
  with patch.dict(os.environ,{'APP_DATA_DIR':str(self.data)}),patch.object(storage,'DATA',self.data):
   a=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run();a.sidebar.date_input[0].set_value(date(2026,9,1)).run();a.sidebar.selectbox[0].set_value('Vistorias').run();a.sidebar.radio[0].set_value('Serviços e Tabela de Preços').run()
   next(v for v in a.selectbox if v.label=='Categoria do critério').set_value('200014105').run()
   next(v for v in a.selectbox if v.label=='Critério de cobrança').set_value('manual');next(v for v in a.text_input if v.label=='Justificativa/documento do critério').set_value('Documento confirmado')
   next(v for v in a.button if v.label=='Calcular impacto do critério').click().run();self.assertFalse(a.exception);self.assertEqual(self.preview()['inspection_cents'],2250)
   next(v for v in a.checkbox if v.label.startswith('Conferi a vigência')).check();next(v for v in a.button if v.label=='Confirmar alteração após impacto').click().run();self.assertFalse(a.exception);self.assertEqual(self.preview()['inspection_cents'],0);self.assertEqual(self.preview()['pending'],2)

class MigrationTests(unittest.TestCase):
 def old_root(self,path,approved=False):
  # Dumps sintéticos reais de 568bc75: reproduzível sem Git/Python antigo no Windows.
  root=path/'vistorias';root.mkdir();fixtures=Path(__file__).parent/'fixtures'
  for bank,name in [('financeiro.sqlite3','inspection-finance-v1.sql'),('vistorias.sqlite3','inspection-operational-v1.sql')]:
   with sqlite3.connect(root/bank) as c:c.executescript((fixtures/name).read_text(encoding='utf-8'))
  if not approved:
   with sqlite3.connect(root/'financeiro.sqlite3') as c:c.execute('DELETE FROM approvals')
  return root
 def test_v1_backup_migration_and_approved_history_unchanged(self):
  with tempfile.TemporaryDirectory() as t:
   root=self.old_root(Path(t),True);bank=root/'financeiro.sqlite3';source=root/'vistorias.sqlite3';sha=hashlib.sha256(source.read_bytes()).hexdigest()
   with sqlite3.connect(bank) as c:payload=c.execute('SELECT payload FROM approvals').fetchone()[0];self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],1)
   with b.connect(root) as c:
    self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],2);self.assertEqual(c.execute('SELECT payload FROM approvals').fetchone()[0],payload);self.assertEqual(c.execute('SELECT SUM(cents) FROM frozen_charges').fetchone()[0],1200)
   self.assertEqual(b.financial(root,'2026-09')['inspection_cents'],1200);self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),sha)
   versions=[]
   for f in (root/'backups').glob('financeiro*.sqlite3'):
    with sqlite3.connect(f) as c:self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok');versions.append(c.execute('PRAGMA user_version').fetchone()[0])
   self.assertIn(1,versions)
 def test_unapproved_existing_records_become_outside_without_deletion(self):
  with tempfile.TemporaryDirectory() as t:
   root=self.old_root(Path(t));self.assertEqual(b.preview(root,'2026-09')['inspection_cents'],0)
   with b.connect(root) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM commercial').fetchone()[0],1)
 def test_migration_failure_rolls_back_schema_and_preserves_backup(self):
  with tempfile.TemporaryDirectory() as t:
   root=self.old_root(Path(t),True)
   with sqlite3.connect(root/'financeiro.sqlite3') as c:
    p=json.loads(c.execute('SELECT payload FROM approvals').fetchone()[0]);p['inspection_cents']+=1;c.execute('UPDATE approvals SET payload=?',(json.dumps(p),))
   with self.assertRaises(ValueError):b.connect(root)
   with sqlite3.connect(root/'financeiro.sqlite3') as c:
    self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],1);self.assertNotIn('city_key',[r[1] for r in c.execute('PRAGMA table_info(commercial)')])
   self.assertTrue(list((root/'backups').glob('financeiro*.sqlite3')))
 def test_missing_operational_source_cancels_migration(self):
  with tempfile.TemporaryDirectory() as t:
   root=self.old_root(Path(t));(root/'vistorias.sqlite3').rename(root/'guardado.sqlite3')
   with self.assertRaises(ValueError):b.connect(root)
   with sqlite3.connect(root/'financeiro.sqlite3') as c:self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],1)
if __name__=='__main__':unittest.main()
