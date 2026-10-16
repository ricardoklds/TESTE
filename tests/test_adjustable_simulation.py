"""Simulação gerencial: centavos exatos, cache e nenhuma gravação financeira."""
from decimal import Decimal,ROUND_HALF_UP
from unittest.mock import patch
from io import BytesIO
import unittest
import openpyxl
import test_simple_interface as fixtures
import contract_finance as contract
import inspection_billing as bill
import contract_reports as reports
from contract_presentation import simulate,compose
from ui_navigation import navigate

class AdjustableSimulation(unittest.TestCase):
 setUp=fixtures.SimpleInterface.setUp
 tearDown=fixtures.SimpleInterface.tearDown
 load=fixtures.SimpleInterface.load
 geo=fixtures.SimpleInterface.geo
 app=fixtures.SimpleInterface.app
 metric=fixtures.SimpleInterface.metric
 bank_hashes=fixtures.SimpleInterface.bank_hashes
 def test_all_percentages_exact_rounding_and_off(self):
  for gross in [0,1,10,9950,9949,59690623]:
   for tenth in range(1,51):
    percent=Decimal(tenth)/10
    expected=int((Decimal(gross)*percent/100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    self.assertEqual(simulate(gross,True,percent),{'gross_cents':gross,'deduction_cents':expected,'net_cents':gross-expected})
    self.assertEqual(simulate(gross,False,percent)['net_cents'],gross)
  self.assertEqual(simulate(100,True,.5)['deduction_cents'],1)
  for percent in [0,.05,5.1,'NaN','Infinity']:
   with self.assertRaises(ValueError):simulate(100,True,percent)
 def test_slider_is_session_only_without_financial_recalculation(self):
  self.load();self.geo()
  with self.app() as a:
   navigate(a,module='Fechamento geral');before=self.bank_hashes();official=contract.state(self.data,'2026-09')
   self.assertFalse(a.slider)
   with patch.object(contract,'preview',side_effect=AssertionError('Recálculo')),patch.object(contract,'apply_fine',side_effect=AssertionError('Multa oficial')),patch.object(bill,'preview',side_effect=AssertionError('Recálculo Vistorias')):
    a.toggle[0].set_value(True).run();self.assertEqual(a.slider[0].value,1.0)
    self.assertEqual((a.slider[0].min,a.slider[0].max,a.slider[0].step),(.1,5.,.1))
    for percent,amount in [(.1,'R$ 0,15'),(2.5,'R$ 3,86'),(5.,'R$ 7,73')]:
     a.slider[0].set_value(percent).run();self.assertFalse(a.exception);self.assertEqual(self.metric(a,'Glosa simulada'),amount)
    a.toggle[0].set_value(False).run();self.assertFalse(a.slider)
    self.assertEqual(self.metric(a,'Glosa simulada'),'R$ 0,00');self.assertEqual(self.metric(a,'Fechamento líquido simulado'),self.metric(a,'Fechamento bruto'))
   self.assertEqual(contract.state(self.data,'2026-09'),official);self.assertEqual(self.bank_hashes(),before)
 def test_preview_uses_rate_and_invalidates_after_slider_change(self):
  from pypdf import PdfReader
  self.load();self.geo()
  with self.app() as a:
   navigate(a,module='Fechamento geral');a.toggle[0].set_value(True).run();a.slider[0].set_value(2.5).run();before=self.bank_hashes()
   next(b for b in a.button if b.label=='Gerar relatório de prévia').click().run();self.assertFalse(a.exception)
   scope,files=a.session_state['managerial_contract_preview']
   w=openpyxl.load_workbook(BytesIO(files['Excel']));rows={r[0]:r[1] for r in w['Resumo Geral'].iter_rows(values_only=True) if len(r)>1}
   self.assertEqual(rows['Glosa simulada de 2,5%'],3.86);w.close()
   text=' '.join(p.extract_text() for p in PdfReader(BytesIO(files['PDF'])).pages);self.assertIn('Glosa simulada de 2,5%',text)
   a.slider[0].set_value(3.).run();self.assertFalse(any(b.label.startswith('Baixar prévia') for b in a.get('download_button')))
   self.assertEqual(self.bank_hashes(),before)
