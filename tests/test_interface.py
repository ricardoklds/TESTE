"""Testa filtros contra uma cópia da base real, sem modificar dados de produção.

Requer data/ com a planilha de um grupo já importada. Em instalação sem dados,
os testes de interface são explicitamente ignorados; testes unitários continuam.
"""
from datetime import date
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from streamlit.testing.v1 import AppTest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('APP_DATA_DIR',str(ROOT/'data')))


def inventory(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


@unittest.skipUnless((SOURCE/'contrato.sqlite3').exists(),'Sem banco real importado para testar a interface')
class InterfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.before=inventory(SOURCE)
        cls.temp=tempfile.TemporaryDirectory()
        cls.copy=Path(cls.temp.name)/'data';shutil.copytree(SOURCE,cls.copy)
        cls.previous=os.environ.get('APP_DATA_DIR');os.environ['APP_DATA_DIR']=str(cls.copy)
        import storage
        cls.previous_data=storage.DATA;storage.DATA=cls.copy

    @classmethod
    def tearDownClass(cls):
        import storage
        storage.DATA=cls.previous_data
        if cls.previous is None:os.environ.pop('APP_DATA_DIR',None)
        else:os.environ['APP_DATA_DIR']=cls.previous
        cls.temp.cleanup()
        assert inventory(SOURCE)==cls.before,'Banco/originais da produção foram modificados'

    def app(self,page):
        at=AppTest.from_file(str(ROOT/'app.py'),default_timeout=90).run()
        at.sidebar.radio[0].set_value(page).run()
        self.assertFalse(at.exception)
        return at

    def test_three_screens_month_day_interval_and_empty_day(self):
        import core,periods,storage
        from exports import money
        old=storage.DATA;storage.DATA=self.copy
        try:
            rows=storage.records('2026-10');prices=storage.month_info('2026-10')['prices']
            maps=periods.import_mappings(storage.imports('2026-10'))
        finally:storage.DATA=old
        self.assertEqual(len(rows),19668)
        baseline=core.fingerprint(rows)
        first,last=periods.month_bounds('2026-10')
        for page in ('Painel inicial','Fechamento mensal','Produtividade'):
            with self.subTest(page=page):
                at=self.app(page)
                expected=core.summarize(periods.valid_records(periods.filter_period(rows,maps,'2026-10',first,last)),prices)
                self.assertEqual(at.metric[0].value,money(sum(r['total_cents'] for r in expected)))
                self.assertTrue(any('R$ 30.454,12' in x.value for x in at.info))
                at.radio(key='period_mode').set_value('Dia específico').run()
                at.date_input(key='period_day_2026-10').set_value(date(2026,10,10)).run()
                self.assertFalse(at.exception)
                self.assertEqual(at.metric[2].value,'19.622')
                at.date_input(key='period_day_2026-10').set_value(date(2026,10,11)).run()
                self.assertFalse(at.exception)
                self.assertEqual(at.metric[0].value,'R$ 0,00')
                self.assertEqual(at.metric[2].value,'0')
                at.radio(key='period_mode').set_value('Intervalo personalizado').run()
                at.date_input(key='period_start_2026-10').set_value(date(2026,10,10)).run()
                at.date_input(key='period_end_2026-10').set_value(date(2026,10,10)).run()
                self.assertFalse(at.exception)
                self.assertEqual(at.metric[2].value,'19.622')
                at.date_input(key='period_end_2026-10').set_value(date(2026,10,9)).run()
                self.assertTrue(any('inicial' in x.value for x in at.error))
                self.assertEqual(at.metric[0].value,'R$ 0,00')
        self.assertEqual(core.fingerprint(rows),baseline)

    def test_month_change_resets_dates_and_reports_remain_monthly(self):
        at=self.app('Painel inicial')
        at.radio(key='period_mode').set_value('Dia específico').run()
        at.date_input(key='period_day_2026-10').set_value(date(2026,10,10)).run()
        at.sidebar.date_input[0].set_value(date(2026,11,1)).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.date_input(key='period_day_2026-11').value,date(2026,11,1))
        self.assertEqual(at.metric[0].value,'R$ 0,00')
        at.sidebar.date_input[0].set_value(date(2026,10,1)).run()
        at.sidebar.radio[0].set_value('Relatórios').run()
        self.assertEqual(at.metric[0].value,'R$ 30.454,12')
        self.assertFalse(at.exception)


if __name__=='__main__':unittest.main()
