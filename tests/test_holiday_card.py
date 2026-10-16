from ui_navigation import set_month
from ui_navigation import navigate
from contextlib import closing
from datetime import date
from io import BytesIO
from pathlib import Path
import hashlib
import unittest
from unittest.mock import patch
import openpyxl
from streamlit.testing.v1 import AppTest
import holidays,storage,queries,managerial,holiday_card_export
import test_managerial as fixtures


def inventory(folder):return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file()}


class HolidayCardTests(unittest.TestCase):
    setUp=fixtures.ManagementTests.setUp
    tearDown=fixtures.ManagementTests.tearDown
    row=fixtures.ManagementTests.row
    load=fixtures.ManagementTests.load
    output=fixtures.ManagementTests.output
    populate=fixtures.ManagementTests.populate

    def export(self,p,filters=None,start=None,end=None):
        data=managerial.overview(storage.DATA,'2026-09',p,start,end,filters)
        return holiday_card_export.prepare(storage.DATA,queries.revision(),'2026-09',start,end,filters or {},data['fee'],data['holiday_cents']),data

    def test_exact_charged_ids_originals_amounts_filters_and_events(self):
        p=self.populate()
        self.load([self.row('00123',**{'Data da Leitura Atual':'08/09/2026','ATC':'Anhembi/SP'}),
                   self.row('00123',**{'Data da Leitura Atual':'09/09/2026','ATC':'Anhembi/SP'})],name='eventos.xlsx')
        holidays.save('2026-09-08','Municipal sintético','Municipal','SP','Anhembi')
        holidays.save('2026-09-09','Estadual sintético','Estadual','SP')
        before=inventory(storage.DATA)
        for filters,start,end in [({},None,None),({'employee':['Alice']},None,None),({'city':['Anhembi/SP'],'group':['01']},'2026-09-08','2026-09-09')]:
            content,data=self.export(p,filters,start,end)
            with closing(openpyxl.load_workbook(BytesIO(content),read_only=True)) as book:
                summary=dict(book['Resumo'].values)
                self.assertEqual(summary['Quantidade'],data['fee'])
                self.assertEqual(round(summary['Valor total (R$)']*100),data['holiday_cents'])
                table=list(book['Leituras 1'].values);head=list(table[0]);rows=table[1:]
                ids=[r[head.index('ID do registro')] for r in rows]
                self.assertEqual(len(ids),len(set(ids)));self.assertEqual(len(ids),data['fee'])
                with closing(managerial.connect(storage.DATA)) as c:
                    charged={r['id'] for r in holidays.charges(c,'2026-09',start,end)}
                self.assertTrue(set(ids)<=charged)
                if not filters:self.assertEqual(set(ids),charged)
                self.assertTrue(all(r[head.index('Código do serviço')]=='200014097' for r in rows))
                self.assertEqual(sum(round(r[-1]*100) for r in rows),data['holiday_cents'])
                if filters.get('city'):
                    self.assertEqual([r[head.index('Fornecimento original')] for r in rows],['00123','00123'])
        self.assertEqual(inventory(storage.DATA),before)

    def test_empty_stale_and_mismatch_do_not_offer_incorrect_excel_or_leak_xml(self):
        p=self.populate();revision=queries.revision()
        from openpyxl.worksheet._writer import ALL_TEMP_FILES
        before=set(ALL_TEMP_FILES)
        for qty,cents,rev,filters,message in [(0,0,revision,{},'Não há'),(2,210,revision-1,{},'mudaram'),
            (3,315,revision,{},'não coincide'),(2,211,revision,{},'não são consistentes')]:
            with self.assertRaisesRegex(ValueError,message):holiday_card_export.prepare(storage.DATA,rev,'2026-09',None,None,filters,qty,cents)
        self.assertEqual(set(ALL_TEMP_FILES),before)

    def test_frozen_holidays_and_delete_restore_preserved(self):
        self.load([self.row('00001')]);holidays.save('2026-09-07','Sintético','Nacional')
        p=storage.month_info('2026-09')['prices']
        storage.set_import_deleted('2026-09',1,True,'Teste')
        self.assertEqual(managerial.overview(storage.DATA,'2026-09',p)['fee'],0)
        storage.set_import_deleted('2026-09',1,False,'Teste');storage.close_month('2026-09')
        holidays.delete(holidays.calendar()[0]['id']);before=inventory(storage.DATA)
        content,data=self.export(p)
        self.assertEqual(data['fee'],1)
        with closing(openpyxl.load_workbook(BytesIO(content),read_only=True)) as book:
            self.assertEqual(dict(book['Resumo'].values)['Quantidade'],1)
        self.assertEqual(inventory(storage.DATA),before)

    def test_panel_is_lazy_quantity_inside_card_and_missing_dates_not_prominent(self):
        p=self.populate();root=Path(__file__).resolve().parents[1]
        before=inventory(storage.DATA)
        with patch.object(holiday_card_export,'prepare',wraps=holiday_card_export.prepare) as prepare:
            at=AppTest.from_file(str(root/'app.py'),default_timeout=60).run()
            set_month(at,date(2026,9,1)).run()
            self.assertFalse(at.exception);self.assertEqual(prepare.call_count,0)
            self.assertEqual(at.metric[2].value,'R$ 2,10')
            self.assertTrue(any('Quantidade: 2 leituras' in c.value for c in at.caption))
            self.assertFalse(any('Registros sem data' in m.label for m in at.metric))
            self.assertFalse(any('registros sem data' in w.value for w in at.warning))
            at.button(key='holiday_card_prepare').click().run()
            self.assertFalse(at.exception);self.assertEqual(prepare.call_count,1)
            self.assertEqual(len(at.get('download_button')),1)
            at.run();self.assertEqual(prepare.call_count,1)
            at.multiselect(key='manager_employee_2026-09').set_value(['Bob']).run()
            self.assertEqual(at.metric[2].value,'R$ 0,00')
            self.assertTrue(at.button(key='holiday_card_prepare').disabled)
            self.assertEqual(len(at.get('download_button')),0)
            navigate(at,'Relatórios')
            self.assertFalse(at.exception)
            self.assertFalse(any(b.key=='holiday_card_prepare' for b in at.button))
            self.assertTrue(any('Registros sem data' in m.label for m in at.metric))
        self.assertEqual(inventory(storage.DATA),before)
        self.assertEqual(storage.records('2026-09')[0]['raw']['Data da Leitura Atual'],'07/09/2026')
