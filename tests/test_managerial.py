from contextlib import closing
from io import BytesIO
from pathlib import Path
import json
import unittest
import openpyxl
from streamlit.testing.v1 import AppTest
import core,storage,holidays,queries,cached_queries,managerial,validar_gerencial
import test_independent_validation as fixtures


class ManagementTests(unittest.TestCase):
    setUp=fixtures.IndependentTests.setUp
    tearDown=fixtures.IndependentTests.tearDown
    row=fixtures.IndependentTests.row
    load=fixtures.IndependentTests.load
    output=fixtures.IndependentTests.output

    def populate(self):
        rows=[self.row(1,**{'Nome do TACE':'Alice','Grupo':'01'}),
              self.row(1,**{'Nome do TACE':'Bob','Grupo':'02','Faturas Impressas':'Não'}),
              self.row(3,**{'Nome do TACE':None,'ATC':None,'Grupo':None,'Data da Leitura Atual':None}),
              self.row(4,**{'Nome do TACE':'Alice','ATC':'ATC ARACARIGUAMA','Fatura Retida':'Sim'}),
              self.row(5,**{'Nome do TACE':'Bob','ATC':'ATC BOCAINA','Causas de Leitura/Não Leitura Atual':'1'}),
              self.row(6,**{'Nome do TACE':'Bob','Data da Leitura Atual':'06/09/2026'}),
              self.row(7,**{'Nome do TACE':'Alice','Faturas Impressas':''})]
        self.load(rows);holidays.save('2026-09-07','Feriado sintético','Nacional');holidays.save('2026-09-06','Domingo sintético','Nacional')
        return storage.month_info('2026-09')['prices']

    def get(self,p,start=None,end=None,filters=None):return managerial.overview(storage.DATA,'2026-09',p,start,end,filters)

    def test_financial_identity_official_criteria_and_all_periods(self):
        p=self.populate();before=(storage.DATA/'contrato.sqlite3').read_bytes()
        for start,end in [(None,None),('2026-09-07','2026-09-07'),('2026-09-01','2026-09-30')]:
            r=self.get(p,start,end);official=queries.overview('2026-09',start,end)
            for k,col in managerial.UNITS.items():
                self.assertEqual(r[col],holidays.overview('2026-09',start,end)['holiday_quantity'] if k=='feriado' else official['units'][k])
            self.assertEqual(r['normal_cents']+r['holiday_cents'],r['total_cents'])
        self.assertEqual(self.get(p)['undated'],1)
        self.assertEqual(self.get(p,'2026-09-01','2026-09-30')['undated'],0)
        self.assertEqual((storage.DATA/'contrato.sqlite3').read_bytes(),before)

    def test_partitions_combinations_and_winner_not_reallocated(self):
        p=self.populate();whole=self.get(p)
        options=managerial.options(storage.DATA,'2026-09')
        self.assertIn('Não informado',options['employee']);self.assertIn('Não informado',options['city'])
        for dim,values in options.items():
            totals=[self.get(p,filters={dim:[v]}) for v in values]
            for key in (*managerial.MEASURES,'normal_cents','holiday_cents','total_cents'):self.assertEqual(sum(r[key] for r in totals),whole[key])
        filtered=self.get(p,filters={'employee':['Bob'],'group':['02'],'city':['ATC AGUDOS']})
        self.assertEqual(filtered['records'],1);self.assertEqual(filtered['fee'],0)
        self.assertEqual(self.get(p,filters={'city':['INEXISTENTE']})['total_cents'],0)
        self.assertEqual(self.get(p,filters={'employee':['Alice','Alice']})['total_cents'],self.get(p,filters={'employee':['Alice']})['total_cents'])
        self.assertEqual(self.get(p,filters=options)['total_cents'],whole['total_cents'])
        n,combos=managerial.page(storage.DATA,'2026-09',p,by=tuple(managerial.DIMS),limit=100)
        self.assertEqual(n,len(combos));self.assertEqual(sum(r['total_cents'] for r in combos),whole['total_cents'])
        with self.assertRaises(ValueError):managerial.page(storage.DATA,'2026-09',p,limit=101)

    def test_export_and_closed_month_delete_restore_cache_refresh(self):
        p=self.populate();path=str(storage.DATA);rev=queries.revision()
        first=cached_queries.management_overview(path,rev,'2026-09',p)
        storage.set_import_deleted('2026-09',1,True,'Teste')
        self.assertEqual(cached_queries.management_overview(path,queries.revision(),'2026-09',p)['total_cents'],0)
        storage.set_import_deleted('2026-09',1,False,'Teste')
        self.assertEqual(self.get(p)['total_cents'],first['total_cents'])
        before=(storage.DATA/'contrato.sqlite3').read_bytes();rev=queries.revision()
        total,rank=managerial.page(path,'2026-09',p)
        _,detail=managerial.page(path,'2026-09',p,by=('city','group','employee'),limit=100)
        x=managerial.excel(path,'2026-09',p,None,None,{},rev)
        with closing(openpyxl.load_workbook(BytesIO(x),read_only=True)) as book:
            cells=list(book['Detalhamento 1'].values)
            self.assertEqual(sum(r[-1] for r in cells[1:]),first['total_cents'])
        self.assertTrue(managerial.pdf(first,'2026-09',None,None,{},rank,detail).startswith(b'%PDF'))
        empty=self.get(p,filters={'employee':['Inexistente']})
        self.assertTrue(managerial.pdf(empty,'2026-09',None,None,{},[],[]).startswith(b'%PDF'))
        self.assertEqual((storage.DATA/'contrato.sqlite3').read_bytes(),before)
        with self.assertRaises(ValueError):managerial.excel(path,'2026-09',p,None,None,{},rev-1)

    def test_frozen_month_filters_preserve_registered_holidays(self):
        self.load([self.row(1)])
        holidays.save('2026-09-07','Sintético','Nacional');storage.close_month('2026-09')
        holidays.delete(holidays.calendar()[0]['id'])
        p=storage.month_info('2026-09')['prices'];before=(storage.DATA/'contrato.sqlite3').read_bytes()
        self.assertEqual(self.get(p)['fee'],1)
        self.assertEqual(self.get(p,filters={'employee':['Funcionário sintético']})['fee'],1)
        self.assertEqual(self.get(p,filters={'employee':['Outro']})['fee'],0)
        self.assertEqual((storage.DATA/'contrato.sqlite3').read_bytes(),before)

    def test_september_audited_reference_is_not_a_target(self):
        p=self.populate();reference=Path(__file__).parent/'references'/'setembro_2026.json'
        result=validar_gerencial.validate(storage.DATA,reference)
        self.assertFalse(result['matches_reference'])
        self.assertEqual(result['total_cents'],self.get(p)['total_cents'])
        self.assertNotEqual(result['delta_cents'],0)
        self.assertTrue(all(result['partition_totals_match'].values()))

    def test_new_daily_group_invalidates_indicators_and_options(self):
        p=self.populate();path=str(storage.DATA);old=queries.revision()
        before=cached_queries.management_overview(path,old,'2026-09',p)
        cached_queries.management_options(path,old,'2026-09')
        self.load([self.row(88,**{'Grupo':'03','Nome do TACE':'Charlie'})],name='novo-grupo.xlsx')
        new=queries.revision();self.assertGreater(new,old)
        now=cached_queries.management_overview(path,new,'2026-09',p)
        self.assertEqual(now['records'],before['records']+1)
        self.assertGreater(now['total_cents'],before['total_cents'])
        options=cached_queries.management_options(path,new,'2026-09')
        self.assertIn('03',options['group']);self.assertIn('Charlie',options['employee'])
        self.assertEqual(cached_queries.management_overview(path,new,'2026-09',p,filters={'group':['03']})['records'],1)

    def test_interface_combined_filters_and_official_report_unchanged(self):
        p=self.populate();root=Path(__file__).resolve().parents[1]
        from datetime import date
        at=AppTest.from_file(str(root/'app.py'),default_timeout=60).run()
        at.sidebar.date_input[0].set_value(date(2026,9,1)).run()
        baseline=self.get(p)
        self.assertFalse(at.exception)
        self.assertEqual(at.metric[0].value,__import__('exports').money(baseline['total_cents']))
        at.sidebar.radio[0].set_value('Relatórios').run()
        at.button(key='manager_clear').click().run()
        at.multiselect(key='manager_employee_2026-09').set_value(['Alice']).run()
        self.assertFalse(at.exception)
        self.assertEqual(at.metric[0].value,__import__('exports').money(self.get(p,filters={'employee':['Alice']})['total_cents']))
        self.assertEqual(next(m.value for m in at.metric if m.label=='Faturamento mensal'),__import__('exports').money(baseline['total_cents']))
        at.button(key='manager_excel').click().run()
        self.assertFalse(at.exception)
        at.sidebar.radio[0].set_value('Painel inicial').run()
        at.multiselect(key='manager_employee_2026-09').set_value(['Bob']).run()
        at.multiselect(key='manager_group_2026-09').set_value(['02']).run()
        at.multiselect(key='manager_city_2026-09').set_value(['ATC AGUDOS']).run()
        self.assertFalse(at.exception)
        r=self.get(p,filters={'employee':['Bob'],'group':['02'],'city':['ATC AGUDOS']})
        self.assertEqual(at.metric[0].value,__import__('exports').money(r['total_cents']))
        at.radio(key='period_mode').set_value('Dia específico').run()
        at.date_input(key='period_day_2026-09').set_value(date(2026,9,6)).run()
        self.assertEqual(at.multiselect(key='manager_group_2026-09').value,['02'])
        self.assertEqual(at.metric[0].value,'R$ 0,00')
        at.radio(key='period_mode').set_value('Mês completo').run()
        at.sidebar.radio[0].set_value('Fechamento mensal').run()
        self.assertFalse(at.exception)
        self.assertEqual(at.metric[0].value,__import__('exports').money(baseline['total_cents']))
