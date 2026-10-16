import json,unittest
from io import BytesIO
from unittest.mock import patch
import openpyxl
import test_simple_interface as fixtures
import inspection_billing as bill
import contract_finance as contract
import contract_reports as reports
from contract_presentation import compose,table_rows
from inspection_price_editor import changes_from_table,price_cents
from ui_navigation import navigate

class ManagerialContract(unittest.TestCase):
 setUp=fixtures.SimpleInterface.setUp
 tearDown=fixtures.SimpleInterface.tearDown
 load=fixtures.SimpleInterface.load
 geo=fixtures.SimpleInterface.geo
 app=fixtures.SimpleInterface.app
 bank_hashes=fixtures.SimpleInterface.bank_hashes
 metric=fixtures.SimpleInterface.metric
 def readings(self):
  import storage,holidays
  import test_independent_validation as source
  with patch.object(storage,'DATA',self.data):
   rows=[source.IndependentTests.row(self,1),source.IndependentTests.row(self,2,**{'Faturas Impressas':'Não'}),source.IndependentTests.row(self,3,**{'Causas de Leitura/Não Leitura Atual':'1'})]
   source.IndependentTests.load(self,rows);holidays.save('2026-09-07','Teste','Nacional')
 def batch(self,**kw):
  s=bill.service_list(self.root,'2026-09');base=[{'Código':r['code'],'Descrição':r['name'],'Valor unitário (R$)':r['cents']/100,'Vigência':'2026-09','Situação':'Ativo'} for r in s]
  base[0].update(kw);changes=changes_from_table(s,base,'2026-09')
  return {'kind':'services','effective':min(r['effective'] for r in changes),'changes':changes,'evidence':'Teste sintético'}
 def test_open_price_table_does_not_recalculate_or_change_prices(self):
  self.load()
  with self.app() as a:
   before=self.bank_hashes()
   with patch.object(bill,'classified_sql',side_effect=AssertionError('Consulta financeira pesada')):
    navigate(a,'Serviços e Preços de Vistorias');self.assertFalse(a.exception)
   self.assertEqual(self.bank_hashes(),before)
 def test_price_batch_edit_inactivate_history_no_delete_and_rollback(self):
  self.load();before=self.bank_hashes();change=self.batch(**{'Valor unitário (R$)':13.0,'Situação':'Inativo'});plan=bill.prepare_change(self.root,change)
  self.assertEqual(self.bank_hashes(),before);self.assertEqual(plan['impact'][0]['after']['pending'],1)
  bill.confirm_change(self.root,plan,True)
  with bill.connect(self.root) as c:
   self.assertEqual(c.execute("SELECT active FROM prices WHERE code='200014104'").fetchone()[0],0);self.assertEqual(c.execute('SELECT COUNT(*) FROM services').fetchone()[0],4)
   self.assertEqual(c.execute("SELECT COUNT(*) FROM audit WHERE json_extract(payload,'$.change.kind')='services'").fetchone()[0],1)
  with self.assertRaises(ValueError):bill.confirm_change(self.root,plan,True)
 def test_batch_atomic_when_one_child_reaches_approved_month(self):
  self.load();self.geo();p=bill.preview(self.root,'2026-09');bill.approve(self.root,'2026-09',p['fingerprint'],'Doc',True);before=self.bank_hashes()
  rows=[{'code':'geo','name':'Geolocalização','cents':1300,'active':True,'effective':'2026-10'},{'code':'200014104','name':'Vistoria de atualização cadastral','cents':1300,'active':True,'effective':'2026-09'}]
  with self.assertRaises(ValueError):bill.prepare_change(self.root,{'kind':'services','effective':'2026-09','changes':rows,'evidence':'Teste'})
  self.assertEqual(self.bank_hashes(),before)
 def test_batch_rolls_back_all_rows_on_invalid_second_service(self):
  self.load();before=self.bank_hashes()
  rows=[{'code':'geo','name':'Geolocalização','cents':1300,'active':True,'effective':'2026-09'},{'code':'200014104','name':'Nome indevidamente alterado','cents':1300,'active':True,'effective':'2026-09'}]
  with self.assertRaises(ValueError):bill.prepare_change(self.root,{'kind':'services','effective':'2026-09','changes':rows,'evidence':'Teste'})
  self.assertEqual(self.bank_hashes(),before)
 def test_table_validation_and_future_price_preserve_current_month(self):
  self.load();change=self.batch(**{'Valor unitário (R$)':13,'Vigência':'2026-10'});plan=bill.prepare_change(self.root,change);bill.confirm_change(self.root,plan,True)
  self.assertEqual(next(r['cents'] for r in bill.service_list(self.root,'2026-09') if r['code']=='200014104'),1200)
  self.assertEqual(next(r['cents'] for r in bill.service_list(self.root,'2026-10') if r['code']=='200014104'),1300)
  for value in ['nan',-1,1.001,None]:
   with self.assertRaises(ValueError):price_cents(value)
 def test_ui_edit_and_deactivation_need_confirmation(self):
  self.load()
  with self.app() as a:
   navigate(a,'Serviços e Preços de Vistorias');key=next(k for k in a.session_state.filtered_state if str(k).startswith('prices:'))
   a.session_state[key]={'edited_rows':{0:{'Valor unitário (R$)':13.0,'Situação':'Inativo'}},'added_rows':[],'deleted_rows':[]}
   next(b for b in a.button if b.label=='Salvar alterações').click().run();self.assertFalse(a.exception)
   next(v for v in a.checkbox if v.label.startswith('Conferi a vigência')).check();next(b for b in a.button if b.label=='Confirmar alteração após impacto').click().run();self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],3450)
   next(v for v in a.checkbox if v.label=='Confirmo a desativação dos serviços indicados').check();next(b for b in a.button if b.label=='Confirmar alteração após impacto').click().run();self.assertFalse(a.exception);self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],2250)
 def test_ui_add_service_and_no_current_mapping_automatically(self):
  self.load()
  with self.app() as a:
   navigate(a,'Serviços e Preços de Vistorias');next(b for b in a.button if b.label=='Adicionar serviço').click().run()
   next(v for v in a.text_input if v.label=='Código do novo serviço').set_value('TESTE-123');next(v for v in a.text_input if v.label=='Descrição do novo serviço').set_value('Serviço sintético')
   next(v for v in a.number_input if v.label=='Valor unitário do novo serviço (R$)').set_value(5.25);next(b for b in a.button if b.label=='Salvar novo serviço').click().run();self.assertFalse(a.exception)
   next(v for v in a.checkbox if v.label.startswith('Conferi a vigência')).check();next(b for b in a.button if b.label=='Confirmar alteração após impacto').click().run();self.assertFalse(a.exception)
   self.assertEqual(next(r['cents'] for r in bill.service_list(self.root,'2026-09') if r['code']=='TESTE-123'),525);self.assertEqual(bill.preview(self.root,'2026-09')['inspection_cents'],3450)
 def test_composition_ten_services_and_informative_subtotal_not_added_twice(self):
  self.load();self.geo();self.readings();p=contract.state(self.data,'2026-09');before=self.bank_hashes();x=compose(self.data,p)
  self.assertEqual(len(x['rows']),10);self.assertEqual(sum(r['cents'] for r in x['rows']),p['gross_cents']);self.assertEqual(x['visits_geo_cents'],15450)
  self.assertEqual(x['gross_cents'],x['subtotals']['Leituras']+x['visits_geo_cents']);self.assertEqual(self.bank_hashes(),before)
  self.assertEqual(len([r for r in x['rows'] if r['component']=='Geolocalização']),1)
  self.assertTrue(all(r['quantity'] for r in x['rows'] if r['component']=='Leituras'))
 def test_mixed_specific_tss_price_no_invented_average(self):
  self.load([('1','VERIFICAR SERVIÇO EXECUTADO','01/09/2026 10:00','Fechada'),('2','EXAME PREDIAL ALTA DE CONSUMO COMP MD','02/09/2026 10:00','Fechada')]);self.geo()
  change={'kind':'rule','tss':'VERIFICAR SERVIÇO EXECUTADO','effective':'2026-09','decision':'Cobrar','code':'200014106','unit_cents':1200,'evidence':'Teste'};plan=bill.prepare_change(self.root,change);bill.confirm_change(self.root,plan,True)
  x=compose(self.data,contract.state(self.data,'2026-09'));r=next(r for r in x['rows'] if r['code']=='200014106')
  self.assertEqual(r['cents'],3450);self.assertIsNone(r['unit_cents']);self.assertEqual({v['unit_cents'] for v in r['rate_details']},{1200,2250});self.assertIn('R$ 12,00',next(r['Valor unitário'] for r in table_rows(x) if r['Código contratual']=='200014106'))
 def test_pdf_excel_separate_components_simulation_only_when_enabled(self):
  from pypdf import PdfReader
  self.load();self.geo();self.readings();p=contract.state(self.data,'2026-09');x=compose(self.data,p);before=self.bank_hashes()
  for enabled in [False,True]:
   blob=reports.excel(x,enabled);w=openpyxl.load_workbook(BytesIO(blob));self.assertEqual(w.sheetnames,['Resumo Geral','Serviços de Leituras','Serviços de Vistorias','Geolocalização'])
   labels=[r[0].value for r in w['Resumo Geral']];self.assertEqual('Glosa simulada de 1%' in labels,enabled)
   self.assertIn('Subtotal informativo: Vistorias + Geolocalização',labels);self.assertEqual(w['Geolocalização']['C4'].value,10);self.assertEqual(w['Geolocalização']['D4'].value,12);w.close()
   blob=reports.pdf(x,enabled);reader=PdfReader(BytesIO(blob));text=' '.join(page.extract_text() for page in reader.pages)
   self.assertIn('NÃO APROVADA',text);self.assertIn('Subtotal informativo: Vistorias + Geolocalização',text);self.assertEqual('Glosa simulada de 1%' in text,enabled);self.assertIn('Adicional de leitura em feriado',text)
  self.assertEqual(self.bank_hashes(),before)
 def test_reports_on_demand_cache_downloads_invalidated_when_toggle_changes(self):
  self.load();self.geo()
  with self.app() as a:
   with patch.object(reports,'pdf',side_effect=AssertionError('PDF automático')),patch.object(reports,'excel',side_effect=AssertionError('Excel automático')):navigate(a,module='Fechamento geral');a.toggle[0].set_value(True).run();self.assertFalse(a.exception)
   before=self.bank_hashes();next(b for b in a.button if b.label=='Gerar relatório de prévia').click().run();self.assertFalse(a.exception);self.assertEqual(self.bank_hashes(),before)
   scope,files=a.session_state['managerial_contract_preview'];self.assertEqual(set(files),{'PDF','Excel'});a.toggle[0].set_value(False).run()
   self.assertFalse(any(b.label.startswith('Baixar prévia') for b in a.get('download_button')))
 def test_generated_preview_invalidates_after_real_data_change(self):
  self.load();self.geo()
  with self.app() as a:
   navigate(a,module='Fechamento geral');next(b for b in a.button if b.label=='Gerar relatório de prévia').click().run();old_scope=a.session_state['managerial_contract_preview'][0]
   bill.save_geo(self.root,'2026-09','Total mensal',11,{})
   a.run();self.assertFalse(a.exception);self.assertFalse(a.get('download_button'))
   next(b for b in a.button if b.label=='Gerar relatório de prévia').click().run();self.assertNotEqual(a.session_state['managerial_contract_preview'][0],old_scope)
 def test_legacy_snapshot_uses_closed_month_prices_only_and_does_not_mutate(self):
  self.load();self.geo();self.readings();p=contract.state(self.data,'2026-09');original=json.dumps(p,sort_keys=True)
  legacy=json.loads(original);legacy['readings'].pop('services')
  # Uma fotografia não comprovável permanece sem detalhes; o total não é forçado.
  x=compose(self.data,legacy);self.assertFalse(x['complete']);self.assertTrue(all(r['quantity'] is None for r in x['rows'] if r['component']=='Leituras'))
  import storage
  with patch.object(storage,'DATA',self.data):
   with storage.connect() as c:c.execute("UPDATE months SET closed=1 WHERE month='2026-09'")
  legacy['readings']['closed']=True;before=self.bank_hashes();x=compose(self.data,legacy);self.assertTrue(x['complete']);self.assertEqual(sum(r['cents'] for r in x['rows']),legacy['gross_cents']);self.assertEqual(self.bank_hashes(),before);self.assertEqual(json.dumps(p,sort_keys=True),original)
if __name__=='__main__':unittest.main()
