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
   self.assertEqual(frame['Registros operacionais'].sum(),sum(r['operational_count'] for r in p['municipalities']))
   self.assertEqual(frame['Faturamento de vistorias'].tolist(),[ui.money(r['cents']) for r in p['municipalities']])
   self.assertEqual(self.bank_hashes(),hashes)

