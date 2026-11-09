from ui_navigation import set_month
from ui_navigation import navigate
from contextlib import closing
from datetime import date
from pathlib import Path
import unittest
import openpyxl
from streamlit.testing.v1 import AppTest
import auditoria_fechamento
import diagnostico_divergencia
import periods
import queries
import storage
import test_auditoria


class ReconciliationTests(unittest.TestCase):
    setUp=test_auditoria.AuditTests.setUp
    tearDown=test_auditoria.AuditTests.tearDown
    import_fixture=test_auditoria.AuditTests.import_fixture

    def test_month_is_accumulated_but_explicit_full_interval_is_dated(self):
        first,last=periods.month_bounds('2026-09')
        self.assertEqual(periods.query_bounds('2026-09','Mês completo',first,last),(None,None))
        self.assertEqual(periods.query_bounds('2026-09','Intervalo personalizado',first,last),('2026-09-01','2026-09-30'))
        self.assertEqual(periods.query_bounds('2026-09','Dia específico',first,first),('2026-09-01','2026-09-01'))
        with self.assertRaises(ValueError):periods.query_bounds('2026-09','Dia específico',first,last)

    def test_exact_ids_and_financial_delta_read_only(self):
        self.import_fixture('fixture.xlsx',['2026-09-07',None,'inválida','2026-10-01'])
        before=(storage.DATA/'contrato.sqlite3').read_bytes()
        root=Path(self.temp.name)
        result=diagnostico_divergencia.diagnose(storage.DATA,root/'diagnostico')
        audited=auditoria_fechamento.audit(storage.DATA,root/'auditoria',check_originals=False)
        self.assertTrue(result['detail_matches_sql']);self.assertTrue(result['audit_sql_matches_monthly'])
        self.assertEqual(result['monthly_cents'],audited['official_total_cents'])
        self.assertEqual(result['monthly_quantities'],audited['official_quantities'])
        self.assertEqual(result['delta_cents'],288)
        self.assertEqual(result['delta_records'],1)
        self.assertEqual(result['monthly_quantities']['feriado'],1)
        self.assertEqual(result['old_screen_quantities']['feriado'],1)
        with closing(openpyxl.load_workbook(root/'diagnostico'/'reconciliacao.xlsx',read_only=True)) as book:
            rows=list(book['Registros da diferença 1'].values)
            self.assertEqual(rows[1][0],2)
            self.assertEqual(rows[1][13],'Sem data projetada')
        self.assertEqual((storage.DATA/'contrato.sqlite3').read_bytes(),before)

    def test_delete_restore_freeze_and_empty_month(self):
        self.import_fixture('fixture.xlsx',['2026-09-07',None])
        storage.set_import_deleted('2026-09',1,True,'teste')
        root=Path(self.temp.name)
        deleted=diagnostico_divergencia.diagnose(storage.DATA,root/'deleted')
        self.assertEqual(deleted['monthly_cents'],0)
        storage.set_import_deleted('2026-09',1,False,'teste')
        storage.close_month('2026-09')
        restored=diagnostico_divergencia.diagnose(storage.DATA,root/'restored')
        self.assertEqual(restored['monthly_cents'],681)
        self.assertTrue(restored['detail_matches_sql'])
        empty=diagnostico_divergencia.diagnose(storage.DATA,root/'empty','2026-08')
        self.assertFalse(empty['available']);self.assertNotIn('monthly_cents',empty)
        with self.assertRaises(ValueError):diagnostico_divergencia.diagnose(storage.DATA,storage.DATA/'no')
        with self.assertRaises(FileExistsError):diagnostico_divergencia.diagnose(storage.DATA,root/'restored')

    def test_three_screens_match_audit_and_daily_does_not_include_undated(self):
        self.import_fixture('fixture.xlsx',['2026-09-07',None])
        root=Path(__file__).resolve().parents[1]
        for page in ('Painel inicial','Fechamento mensal','Produtividade'):
            at=AppTest.from_file(str(root/'app.py'),default_timeout=60).run()
            set_month(at,date(2026,9,1)).run()
            navigate(at,page)
            at.radio(key='period_mode').set_value('Mês completo').run()
            self.assertFalse(at.exception)
            self.assertEqual(at.metric[0].value,'R$ 6,81')
            at.radio(key='period_mode').set_value('Dia específico').run()
            at.date_input(key='period_day_2026-09').set_value(date(2026,9,7)).run()
            self.assertFalse(at.exception)
            self.assertEqual(at.metric[0].value,'R$ 3,93')
            navigate(at,'Relatórios')
            self.assertEqual(at.metric[0].value,'R$ 6,81')
