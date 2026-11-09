"""Anual: contratos somente leitura, metas gerenciais e médias consecutivas."""
from decimal import Decimal
from pathlib import Path
from io import BytesIO
import unittest,tempfile,json,hashlib,sqlite3,time
from unittest.mock import patch
import annual_billing as annual
import annual_reports as reports
import test_simple_interface as fixtures
import test_managerial_contract as finance_fixtures
import contract_finance as contract
import inspection_billing as billing
from ui_navigation import navigate

class AnnualMath(unittest.TestCase):
 def row(self,month,cents,approved=True,complete=True):
  return {'month':month,'readings_cents':cents,'visits_cents':0,'geo_cents':0,'gross_cents':cents,'approved':approved,'complete':complete,'status':'Aprovado' if approved else 'Provisório','notes':''}
 def test_example_and_missing_not_zero(self):
  data={m:self.row(m,v) for m,v in [('2026-01',72000000),('2026-02',72000000),('2026-03',59000000)]}
  r=annual.analyze(data,2026,3);self.assertEqual(r['rows'][2]['rolling_cents'],67666667);self.assertIsNone(r['rows'][0]['rolling_cents']);self.assertIsNone(r['rows'][3]['gross_cents']);self.assertEqual(r['accumulated_cents'],203000000);self.assertLess(r['rows'][2]['difference_cents'],0);self.assertGreater(r['rows'][2]['rolling_difference_cents'],0)
  data.pop('2026-02');self.assertIsNone(annual.analyze(data,2026,3)['rows'][2]['rolling_cents'])
 def test_all_windows_cross_year_complete_provisional_and_zero(self):
  for window in [3,6,12]:
   data={annual.shift('2026-01',-i):self.row(annual.shift('2026-01',-i),10000) for i in range(window)}
   r=annual.analyze(data,2026,window)['rows'][0];self.assertEqual(r['rolling_cents'],10000);self.assertEqual(r['rolling_status'],'Apenas aprovados')
   data['2026-01']=self.row('2026-01',0,False);r=annual.analyze(data,2026,window)['rows'][0];self.assertIsNotNone(r['rolling_cents']);self.assertEqual(r['rolling_status'],'Inclui provisórios')
   data['2026-01']['complete']=False;self.assertIsNone(annual.analyze(data,2026,window)['rows'][0]['rolling_cents'])
 def test_variable_goals_history_and_no_banks_created(self):
  with tempfile.TemporaryDirectory() as d:
   self.assertEqual(annual.goals(d),[]);self.assertEqual(annual.monthly(d,'2025-02','2026-12'),{});self.assertEqual(list(Path(d).iterdir()),[])
   annual.save_goal(d,'2026-03','700000.00');annual.save_goal(d,'2026-07','600000');annual.save_goal(d,'2026-03','710000')
   h=annual.goals(d);self.assertEqual(len(h),3);self.assertEqual(annual.target(h,'2026-02'),65000000);self.assertEqual(annual.target(h,'2026-03'),71000000);self.assertEqual(annual.target(h,'2026-08'),60000000)
   self.assertFalse(list(Path(d).rglob('*.sqlite3')))
   for bad in ['NaN',0,-1,'1.001']:
    with self.assertRaises(ValueError):annual.save_goal(d,'2026-01',bad)
   with self.assertRaises(ValueError):annual.save_goal(d,'2026-13',100)
 def test_indicators_do_not_mix_incomplete_best_and_average(self):
  data={m:self.row(m,c,approved=a,complete=f) for m,c,a,f in [('2026-01',100,True,True),('2026-02',300,False,True),('2026-03',9999,False,False)]}
  r=annual.analyze(data,2026,3);self.assertEqual(r['average_cents'],200);self.assertEqual(r['best']['month'],'2026-02');self.assertEqual(r['approved_cents'],100);self.assertEqual(r['provisional_cents'],10299);self.assertIsNone(r['current']['rolling_cents'])
 def test_exports_values_missing_cells_and_provisional_labels(self):
  import openpyxl
  from pypdf import PdfReader
  data={'2026-01':self.row('2026-01',123456,False)};r=annual.analyze(data,2026,3)
  w=openpyxl.load_workbook(BytesIO(reports.excel(r)));s=w['Competências'];self.assertEqual(s['E2'].value,1234.56);self.assertIsNone(s['E3'].value);self.assertEqual(s['J2'].value,'Provisório');self.assertEqual(s.max_row,13);w.close()
  text=' '.join(p.extract_text() for p in PdfReader(BytesIO(reports.pdf(r))).pages);self.assertIn('Provisório',text);self.assertIn('Histórico insuficiente',text)

class AnnualIntegration(unittest.TestCase):
 setUp=fixtures.SimpleInterface.setUp
 tearDown=fixtures.SimpleInterface.tearDown
 load=fixtures.SimpleInterface.load
 geo=fixtures.SimpleInterface.geo
 app=fixtures.SimpleInterface.app
 bank_hashes=fixtures.SimpleInterface.bank_hashes
 readings=finance_fixtures.ManagerialContract.readings
 def test_existing_totals_identical_and_all_access_readonly(self):
  self.load();self.geo();self.readings();official=contract.state(self.data,'2026-09');before=self.bank_hashes()
  with patch.object(billing,'connect',side_effect=AssertionError('Abertura de escrita Vistorias')),patch.object(contract,'connect',side_effect=AssertionError('Abertura de escrita Geral')):
   rows=annual.monthly(self.data,'2025-02','2026-12')
  r=rows['2026-09'];self.assertEqual(r['gross_cents'],official['gross_cents']);self.assertEqual(r['readings_cents'],official['readings']['cents']);self.assertTrue(r['complete']);self.assertFalse(r['approved']);self.assertEqual(self.bank_hashes(),before)
 def test_approved_snapshot_gross_ignores_any_deduction(self):
  self.load();self.geo();self.readings();p=contract.preview(self.data,'2026-09')
  with contract.connect(self.data) as c:
   c.execute('INSERT INTO closings VALUES(?,?,?,?)',('2026-09',json.dumps(p),'now','fixture'))
   c.execute('INSERT INTO deductions VALUES(?,?,?,?)',('2026-09',json.dumps({'cents':99999}),'now','fixture'))
  before=self.bank_hashes()
  with patch.object(contract,'readings',side_effect=AssertionError('Snapshot recalculado')),patch.object(billing,'preview',side_effect=AssertionError('Snapshot recalculado')):
   r=annual.monthly(self.data,'2026-01','2026-12')['2026-09']
  self.assertTrue(r['approved']);self.assertEqual(r['gross_cents'],p['gross_cents']);self.assertEqual(self.bank_hashes(),before)
 def test_missing_geo_is_incomplete_and_goals_do_not_touch_financial_history(self):
  self.load();self.readings();before=self.bank_hashes();r=annual.monthly(self.data,'2026-01','2026-12')['2026-09'];self.assertFalse(r['complete']);self.assertIsNone(r['geo_cents'])
  previous=annual.version(self.data,False);annual.save_goal(self.data,'2026-09','700000');self.assertEqual(annual.version(self.data,False),previous);self.assertEqual(self.bank_hashes(),before)
 def test_ui_cache_filter_and_exports_are_on_demand(self):
  self.load();self.geo();self.readings()
  with self.app() as a:
   before=self.bank_hashes();navigate(a,'Faturamento Anual');self.assertFalse(a.exception)
   self.assertEqual(a.dataframe[-1].value.shape[0],12)
   import annual_ui
   with patch.object(annual_ui.api,'monthly',side_effect=AssertionError('Consulta financeira repetida')),patch.object(reports,'pdf',side_effect=AssertionError('PDF automático')),patch.object(reports,'excel',side_effect=AssertionError('Excel automático')):
    a.selectbox(key='annual_window').set_value(6).run();self.assertFalse(a.exception)
    next(s for s in a.selectbox if s.label=='Visualizar componente').set_value('Geolocalização').run();self.assertFalse(a.exception)
   next(b for b in a.button if b.label=='Gerar relatórios anuais PDF e Excel').click().run();self.assertFalse(a.exception)
   self.assertEqual(self.bank_hashes(),before)
