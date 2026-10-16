"""Regressões de navegação mensal e apresentação, com bancos temporários."""
from datetime import date
from unittest.mock import patch
import unittest
import inspection_module_ui as ui
import test_simple_interface as fixtures
from ui_navigation import navigate,set_month

class VisualUsability(unittest.TestCase):
 setUp=fixtures.SimpleInterface.setUp
 tearDown=fixtures.SimpleInterface.tearDown
 load=fixtures.SimpleInterface.load
 geo=fixtures.SimpleInterface.geo
 app=fixtures.SimpleInterface.app
 metric=fixtures.SimpleInterface.metric
 bank_hashes=fixtures.SimpleInterface.bank_hashes
 def test_month_selection_has_no_day_and_preserves_totals(self):
  self.load();self.geo()
  with self.app() as a:
   self.assertFalse(a.sidebar.date_input)
   navigate(a,module='Fechamento geral');before=self.metric(a,'Fechamento bruto');hashes=self.bank_hashes()
   set_month(a,date(2026,10,31)).run();self.assertFalse(a.exception)
   set_month(a,date(2026,9,30)).run();self.assertFalse(a.exception)
   self.assertEqual(self.metric(a,'Fechamento bruto'),before)
   self.assertEqual(self.bank_hashes(),hashes)
 def test_city_productivity_reuses_cached_financial_totals(self):
  self.load()
  with self.app() as a:
   navigate(a,'Painel de Vistorias');hashes=self.bank_hashes()
   p=ui.cached_preview(str(self.root),'2026-09',ui.api.revision(str(self.root)))
   with patch.object(ui.api,'financial',side_effect=AssertionError('Recalculo desnecessario')),patch.object(ui.api,'municipal_summary',side_effect=AssertionError('Consulta adicional')):
    navigate(a,'Produtividade de Vistorias');self.assertFalse(a.exception)
   frame=a.dataframe[0].value
   self.assertEqual(frame['Vistorias faturáveis'].sum(),sum(r['billed_count'] for r in p['municipalities']))
   self.assertEqual(frame['Vistorias realizadas'].sum(),sum(r['operational_count'] for r in p['municipalities']))
   self.assertEqual(dict(zip(frame['Município'],frame['Faturamento (R$)'])),{r['municipality'] or 'Não informado':ui.money(r['cents']) for r in p['municipalities']})
   self.assertEqual(self.bank_hashes(),hashes)

 def test_productivity_ordering_changes_only_presentation(self):
  self.load()
  with self.app() as a:
   navigate(a,'Produtividade de Vistorias');hashes=self.bank_hashes()
   rows=[{'municipality':'ZETA','operational_count':3,'billed_count':2,'cents':123456,'pending':1},
         {'municipality':'ALFA','operational_count':10,'billed_count':9,'cents':2250,'pending':0},
         {'municipality':'BETA','operational_count':1,'billed_count':0,'cents':0,'pending':1}]
   preview={'municipalities':rows,'sync_pending':False,'approved':False,'undated':0}
   with patch.object(ui,'cached_preview',return_value=preview),patch.object(ui.api,'financial',side_effect=AssertionError('Recalculo')),patch.object(ui.api,'municipal_summary',side_effect=AssertionError('Consulta adicional')):
    for order,expected in [('Maior quantidade primeiro',['ALFA','ZETA','BETA']),('Menor quantidade primeiro',['BETA','ZETA','ALFA']),('Ordem alfabética dos municípios',['ALFA','BETA','ZETA'])]:
     a.selectbox(key='inspection_productivity_order').set_value(order).run();self.assertFalse(a.exception)
     frame=a.dataframe[0].value
     self.assertEqual(frame.columns.tolist(),['Município','Vistorias realizadas','Vistorias faturáveis','Faturamento (R$)','Pendências'])
     self.assertEqual(frame['Município'].tolist(),expected)
     self.assertEqual(frame['Vistorias realizadas'].sum(),14)
     self.assertEqual(frame['Vistorias faturáveis'].sum(),11)
     self.assertEqual(frame.loc[frame['Município']=='ZETA','Faturamento (R$)'].iloc[0],'R$ 1.234,56')
   self.assertEqual(self.bank_hashes(),hashes)
   self.assertEqual(rows[0]['municipality'],'ZETA')
