import ast,json,unittest
from pathlib import Path
from unittest.mock import patch
import test_simple_interface as fixtures
import inspection_billing as bill
import inspection_contract as policy
import contract_finance as contract
from ui_navigation import navigate

class NoDocuments(unittest.TestCase):
 setUp=fixtures.SimpleInterface.setUp
 tearDown=fixtures.SimpleInterface.tearDown
 load=fixtures.SimpleInterface.load
 app=fixtures.SimpleInterface.app
 bank_hashes=fixtures.SimpleInterface.bank_hashes
 def test_all_catalog_changes_calculate_and_save_without_evidence(self):
  self.load();before=bill.preview(self.root,'2026-09')['inspection_cents']
  changes=[{'kind':'rule','tss':'VISTORIA CADASTRAL','decision':'Cobrar','code':'200014104'}, {'kind':'service','code':'geo','name':'Geolocalização','cents':1200,'active':True}, {'kind':'scope','allowed':policy.ALLOWED,'excluded':policy.EXCLUDED},{'kind':'billing_mode','code':'200014105','mode':'once'}]
  for change in changes:
   change.update(effective='2026-09',evidence=None)
   plan=bill.prepare_change(self.root,change);self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],before)
   bill.confirm_change(self.root,plan,True);self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],before)
  with bill.connect(self.root) as c:self.assertTrue(c.execute("SELECT evidence FROM rules WHERE tss='VISTORIA CADASTRAL'").fetchone()[0])
 def test_legacy_methods_accept_absent_blank_and_none_without_losing_history(self):
  self.load()
  for value in ['',None]:
   bill.save_service(self.root,'geo','Geolocalização','2026-10',1200,True,value)
   bill.save_rule(self.root,'VISTORIA CADASTRAL','','','2026-09','Cobrar','200014104',value)
   bill.review(self.root,1,'2026-09','Cobrar','200014104',value)
  with bill.connect(self.root) as c:
   count=c.execute('SELECT COUNT(*) FROM audit').fetchone()[0];historic=c.execute('SELECT payload FROM audit ORDER BY id LIMIT 1').fetchone()[0]
  bill.save_geo(self.root,'2026-09','Total mensal',0,{})
  p=bill.preview(self.root,'2026-09');bill.approve(self.root,'2026-09',p['fingerprint'],confirmed=True)
  with bill.connect(self.root) as c:
   self.assertGreater(c.execute('SELECT COUNT(*) FROM audit').fetchone()[0],count);self.assertEqual(c.execute('SELECT payload FROM audit ORDER BY id LIMIT 1').fetchone()[0],historic)
   self.assertTrue(c.execute('SELECT evidence FROM approvals').fetchone()[0])
  with self.assertRaises(ValueError):bill.save_rule(self.root,'VISTORIA CADASTRAL','','','2026-09','Excluir',None)
 def test_approve_general_without_document_preserves_consistency_and_snapshot(self):
  self.load();bill.save_geo(self.root,'2026-09','Total mensal',0,{})
  p=bill.preview(self.root,'2026-09');bill.approve(self.root,'2026-09',p['fingerprint'],confirmed=True)
  with patch.object(contract,'readings',return_value={'cents':100000,'closed':True,'revision':1}):
   p=contract.preview(self.data,'2026-09');contract.approve(self.data,'2026-09',bill.digest(p),confirmed=True)
  s=contract.state(self.data,'2026-09');self.assertTrue(s['validated']);self.assertEqual(s['gross_cents'],103450)
  with self.assertRaises(ValueError):contract.approve(self.data,'2026-09','stale',confirmed=True)
 def test_ui_catalog_scope_and_rules_have_no_document_fields_or_confirm_checkboxes(self):
  self.load()
  with self.app() as a:
   for page in ['Serviços e Preços de Vistorias','Municípios do Contrato','Regras comerciais de Vistorias']:
    navigate(a,page);self.assertFalse(a.exception)
    self.assertFalse(any(any(w in t.label.casefold() for w in ['document','justific','responsável','evidência']) for t in a.text_input));self.assertFalse(a.checkbox)
   navigate(a,'Serviços e Preços de Vistorias');next(s for s in a.selectbox if s.label=='Descrição TSS para editar').set_value('VISTORIA CADASTRAL').run()
   next(b for b in a.button if b.label=='Calcular impacto da classificação').click().run();self.assertFalse(a.exception);self.assertFalse(a.error);self.assertFalse(a.checkbox)
   next(b for b in a.button if b.label=='Confirmar alteração após impacto').click().run();self.assertFalse(a.exception);self.assertFalse(a.error)
 def test_vistoria_approval_one_button_no_mandatory_export_or_document(self):
  self.load();bill.save_geo(self.root,'2026-09','Total mensal',0,{})
  with self.app() as a:
   navigate(a,'Faturamento de Vistorias');button=next(b for b in a.button if b.label=='Aprovar faturamento mensal');self.assertFalse(button.disabled)
   self.assertFalse(any('document' in t.label.casefold() or 'responsável' in t.label.casefold() for t in a.text_input))
   button.click().run();self.assertFalse(a.exception);self.assertTrue(bill.financial(self.root,'2026-09')['approved'])
 def test_reading_operations_without_reason_restore_same_financial_results(self):
  import storage
  import test_independent_validation as source
  with patch.object(storage,'DATA',self.data):
   source.IndependentTests.load(self,[source.IndependentTests.row(self,1)])
   entry=storage.imports('2026-09')[0]['id'];row=storage.records('2026-09')[0]['id']
   storage.set_import_deleted('2026-09',entry,True);storage.set_import_deleted('2026-09',entry,False)
   storage.exclude('2026-09',row);storage.exclude('2026-09',row,excluded=False)
   storage.close_month('2026-09');storage.close_month('2026-09',False)
   self.assertFalse(storage.month_info('2026-09')['closed']);self.assertFalse(storage.records('2026-09')[0]['excluded'])
   self.assertTrue(storage.audit('2026-09'))
 def test_brazil_confirmation_no_document_and_no_automatic_locality_invention(self):
  import storage,holidays,localities
  import test_independent_validation as source
  with patch.object(storage,'DATA',self.data):
   source.IndependentTests.load(self,[source.IndependentTests.row(self,1,**{'ATC':'LOCALIDADE DESCONHECIDA'})]);holidays.save('2026-09-07','Teste','Nacional')
   self.assertEqual(holidays.overview('2026-09')['holiday_quantity'],0)
   localities.prove_brazil(storage.imports('2026-09')[0]['id'])
   self.assertEqual(holidays.overview('2026-09')['holiday_quantity'],1)
   with storage.connect() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM municipality_bindings').fetchone()[0],0)
 def test_no_document_widgets_or_official_fine_controls_anywhere(self):
  # AST verifica widgets reais, sem confundir referências históricas com formulários.
  root=Path(__file__).resolve().parents[1]
  for name in ['inspection_module_ui.py','inspection_settings_ui.py','contract_ui.py','inspections_ui.py','readings_ui.py','inspection_price_editor.py']:
   tree=ast.parse((root/name).read_text())
   for node in ast.walk(tree):
    if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr in ['text_input','text_area'] and node.args and isinstance(node.args[0],ast.Constant):
     label=str(node.args[0].value).casefold();self.assertFalse(any(w in label for w in ['document','justific','responsável','evidência']),label)
  self.load()
  with self.app() as a:
   navigate(a,module='Fechamento geral');self.assertFalse(any(b.label=='Aplicar multa' for b in a.button));self.assertTrue(any(t.label=='Aplicar glosa simulada' for t in a.toggle))
if __name__=='__main__':unittest.main()
