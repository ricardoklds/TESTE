from ui_navigation import navigate
import hashlib,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from io import BytesIO
import openpyxl
import inspection_billing as bill
import validar_vistorias
import test_modular_finance as fixtures
class CatalogChanges(unittest.TestCase):
 setUp=fixtures.ModularFinanceTests.setUp
 tearDown=fixtures.ModularFinanceTests.tearDown
 load=fixtures.ModularFinanceTests.load
 geo=fixtures.ModularFinanceTests.geo
 def change(self,**kw):return {'kind':'rule','tss':'VISTORIA CADASTRAL','cause':'','form':'','effective':'2026-09','decision':'Cobrar','code':'200014106','unit_cents':None,'evidence':'Documento de teste',**kw}
 def test_preview_rollback_and_explicit_confirmation(self):
  self.load();before=bill.preview(self.root,'2026-09');sha=hashlib.sha256((self.root/'financeiro.sqlite3').read_bytes()).hexdigest()
  p=bill.prepare_change(self.root,self.change());self.assertEqual(p['impact'][0]['delta_cents'],1050)
  self.assertEqual(hashlib.sha256((self.root/'financeiro.sqlite3').read_bytes()).hexdigest(),sha)
  self.assertEqual(bill.preview(self.root,'2026-09')['fingerprint'],before['fingerprint'])
  with self.assertRaises(ValueError):bill.confirm_change(self.root,p,False)
  bill.confirm_change(self.root,p,True);self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],4500)
  with self.assertRaises(ValueError):bill.confirm_change(self.root,p,True)
 def test_specific_price_does_not_change_other_tss_and_independent(self):
  content=self.load();p=bill.prepare_change(self.root,self.change(unit_cents=1200));bill.confirm_change(self.root,p,True)
  self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],3450)
  predial=next(r for r in bill.preview(self.root,'2026-09')['services'] if r['code']=='200014106');self.assertEqual(predial['quantity'],2);self.assertIsNone(predial['unit_cents'])
  self.assertEqual(next(s for s in bill.service_list(self.root,'2026-09') if s['code']=='200014106')['cents'],2250)
  f=self.data/'source.xlsx';f.write_bytes(content);r=validar_vistorias.run([f],'2026-09',self.data/'audit',bill.export_catalog(self.root,'2026-09'),progress=lambda _:None)
  self.assertEqual(r['total_cents'],3450)
 def test_pending_unknown_excluded_new_tss_and_historical_freeze(self):
  self.load();p=bill.prepare_change(self.root,self.change(decision='Pendente'));bill.confirm_change(self.root,p,True)
  self.assertEqual(bill.preview(self.root,'2026-09')['pending'],1)
  p=bill.prepare_change(self.root,self.change(decision='Excluir'));bill.confirm_change(self.root,p,True);self.assertEqual(bill.preview(self.root,'2026-09')['pending'],0)
  self.geo();p=bill.preview(self.root,'2026-09');bill.approve(self.root,'2026-09',p['fingerprint'],'Doc',True);snapshot=bill.financial(self.root,'2026-09')
  with self.assertRaises(ValueError):bill.prepare_change(self.root,self.change())
  p=bill.prepare_change(self.root,self.change(effective='2026-10',unit_cents=0));bill.confirm_change(self.root,p,True)
  self.assertEqual(bill.financial(self.root,'2026-09'),snapshot)
  p=bill.prepare_change(self.root,self.change(tss='NOVA DESCRIÇÃO',effective='2026-10',decision='Pendente'));bill.confirm_change(self.root,p,True)
  self.assertEqual(next(r for r in bill.catalog_state(self.root)['rules'] if r['tss']=='NOVA DESCRICAO')['decision'],'Pendente')
 def test_service_price_impact_and_stale_plan(self):
  self.load();name=next(s['name'] for s in bill.service_list(self.root,'2026-09') if s['code']=='200014104')
  p=bill.prepare_change(self.root,{'kind':'service','code':'200014104','name':name,'cents':1500,'active':True,'effective':'2026-09','evidence':'Reajuste'})
  self.assertEqual(p['impact'][0]['delta_cents'],300)
  bill.save_geo(self.root,'2026-09','Total mensal',0,{},'Doc')
  with self.assertRaises(ValueError):bill.confirm_change(self.root,p,True)
 def test_catalog_correction_old_install_is_explicit(self):
  self.load([('1','VERIFICAR SERVIÇO EXECUTADO','01/09/2026 10:00','Fechada')]);self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],2250)
  bill.save_rule(self.root,'VERIFICAR SERVIÇO EXECUTADO','','','2026-09','Cobrar','200014104','Catálogo anterior equivocado')
  p=bill.prepare_change(self.root,self.change(tss='VERIFICAR SERVIÇO EXECUTADO'));self.assertEqual(p['impact'][0]['delta_cents'],1050)
  self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],1200)
  bill.confirm_change(self.root,p,True);self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],2250)
 def test_unit_price_expiry_and_month_effectivity(self):
  self.load();p=bill.prepare_change(self.root,self.change(unit_cents=500));bill.confirm_change(self.root,p,True)
  p=bill.prepare_change(self.root,self.change(unit_cents=None));bill.confirm_change(self.root,p,True)
  self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],4500)
  catalog=bill.export_catalog(self.root,'2026-09');self.assertIsNone(catalog['tss_prices']['VISTORIA CADASTRAL']['cents'])
 def test_future_rates_and_impact_cover_only_affected_open_months(self):
  self.load([('1','VISTORIA CADASTRAL','01/09/2026 10:00','Fechada'),('2','VISTORIA CADASTRAL','01/10/2026 10:00','Fechada'),('3','VISTORIA CADASTRAL','01/11/2026 10:00','Fechada')])
  p=bill.prepare_change(self.root,self.change(unit_cents=500));self.assertEqual([r['month'] for r in p['impact']],['2026-09','2026-10','2026-11']);bill.confirm_change(self.root,p,True)
  p=bill.prepare_change(self.root,self.change(effective='2026-11',unit_cents=None));self.assertEqual([r['month'] for r in p['impact']],['2026-11']);bill.confirm_change(self.root,p,True)
  self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],500)
  self.assertEqual(bill.preview(self.root,'2026-10')['inspection_cents'],500)
  self.assertEqual(bill.preview(self.root,'2026-11')['inspection_cents'],2250)
 def test_ui_two_phase_change(self):
  from streamlit.testing.v1 import AppTest
  import os,storage
  self.load()
  with patch.dict(os.environ,{'APP_DATA_DIR':str(self.data)}),patch.object(storage,'DATA',self.data):
   a=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=30).run();navigate(a,module='Vistorias');navigate(a,'Serviços e Tabela de Preços')
   next(s for s in a.selectbox if s.label=='Descrição TSS para editar').set_value('VISTORIA CADASTRAL').run()
   next(s for s in a.selectbox if s.label=='Categoria para cobrança').set_value('200014106')
   next(t for t in a.text_input if t.label=='Competência inicial da classificação').set_value('2026-09')
   next(b for b in a.button if b.label=='Calcular impacto da classificação').click().run();self.assertFalse(a.exception)
   self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],3450)
   next(b for b in a.button if b.label=='Confirmar alteração após impacto').click().run();self.assertFalse(a.exception)
   self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],4500)
if __name__=='__main__':unittest.main()
