from ui_navigation import navigate
"""Filtros de conferência em bancos sintéticos; nenhuma decisão financeira."""
from datetime import date
from contextlib import closing
import hashlib
from io import BytesIO
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import openpyxl
from streamlit.testing.v1 import AppTest
import core,storage,holidays,holiday_review,queries,cached_queries


class HolidayReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.previous=storage.DATA
        storage.DATA=Path(self.temp.name)
        with storage.connect():pass
        holidays.save('2026-09-07','Teste nacional','Nacional')

    def tearDown(self):
        storage.DATA=self.previous;self.temp.cleanup()

    def add(self,supply,city='ATC AGUDOS',day='2026-09-07',employee='Teste A',group='01',note='',task='Leitura'):
        raw=dict(zip(core.FIELDS.values(),['Sim','Não',None,2,'1',employee,city,day,supply,task,group]))
        raw['Observação de teste']=note
        book=openpyxl.Workbook();sheet=book.active;sheet.append(list(raw));sheet.append(list(raw.values()))
        content=BytesIO();book.save(content)
        parsed=core.parse_excel(content.getvalue())[0]
        storage.import_sheet(content.getvalue(),'sintetico.xlsx',parsed,parsed['mapping'],'2026-09')
        return storage.imports('2026-09')[-1]['id']

    def totals(self):return queries.overview('2026-09'),holidays.overview('2026-09')

    def test_four_filters_reasons_and_financial_totals_unchanged(self):
        self.add('1');self.add('1',note='duplicado',employee='Teste B')
        self.add('2',city='Origem desconhecida');self.add('3',day='2026-09-06')
        self.add('',task='');self.add('4');self.add('4',city='ATC ARACARIGUAMA',note='divergente')
        before=self.totals()
        count,all_rows=holiday_review.page('2026-09')
        self.assertEqual(count,7)
        self.assertEqual(holiday_review.page('2026-09',situation='Elegíveis cobrados')[0],1)
        self.assertEqual(holiday_review.page('2026-09',situation='Pendências')[0],5)
        self.assertEqual(holiday_review.page('2026-09',situation='Não cobrados')[0],6)
        reasons=holiday_review.pending_summary('2026-09')
        self.assertEqual(sum(r['Quantidade'] for r in reasons),before[1]['holiday_pending'])
        self.assertIn({'Motivo':'Localidades divergentes na mesma execução','Quantidade':2},reasons)
        self.assertTrue(any('duplicada' in row['reason'] for row in all_rows))
        self.assertEqual(self.totals(),before)
        with patch.object(holiday_review,'statistics',wraps=holiday_review.statistics) as grouped:
            cached_queries.holiday_page(str(storage.DATA),queries.revision(),'2026-09',None,None,0,2,situation='Todos')
            cached_queries.holiday_page(str(storage.DATA),queries.revision(),'2026-09',None,None,0,2,situation='Pendências')
            cached_queries.holiday_page(str(storage.DATA),queries.revision(),'2026-09',None,None,2,2,situation='Pendências')
            cached_queries.holiday_pending_summary(str(storage.DATA),queries.revision(),'2026-09',None,None)
            self.assertEqual(grouped.call_count,1)
        # Filtering away the owner cannot charge the remaining duplicate.
        self.assertEqual(holiday_review.page('2026-09',employee='Teste B',situation='Elegíveis cobrados')[0],0)
        self.assertEqual(holiday_review.page('2026-09',employee='Teste B',situation='Não cobrados')[0],1)

    def test_pagination_filters_and_no_bulk_financial_reads(self):
        for i in range(5):self.add(str(i),city='Desconhecido',employee='Teste A' if i<3 else 'Teste B')
        with patch.object(storage,'records',side_effect=AssertionError('leitura integral proibida')):
            count,first=holiday_review.page('2026-09',limit=2,situation='Pendências')
            _,second=holiday_review.page('2026-09',limit=2,offset=2,situation='Pendências')
            self.assertEqual(count,5);self.assertEqual(len(first),2)
            self.assertFalse({r['id'] for r in first}&{r['id'] for r in second})
            self.assertEqual(holiday_review.page('2026-09',employee='Teste A',situation='Pendências')[0],3)
            self.assertEqual(holiday_review.page('2026-09','2026-09-08','2026-09-08')[0],0)
        for kwargs in [{'limit':501},{'offset':-1},{'situation':'inválido'}]:
            with self.assertRaises(ValueError):holiday_review.page('2026-09',**kwargs)

    def test_excel_complete_fields_filtered_rows_and_db_unchanged(self):
        self.add('1',city='Desconhecido');self.add('2',city='Desconhecido',employee='Teste B')
        self.add('3')
        db=storage.DATA/'contrato.sqlite3';before=db.read_bytes();revision=queries.revision()
        output=holiday_review.pending_excel(db,revision,'2026-09',employee='Teste B')
        with closing(openpyxl.load_workbook(output,read_only=True)) as book:
            sheet=book['Pendências 1'];rows=list(sheet.values)
            self.assertEqual(rows[0],tuple(holiday_review.FIELDS.values()))
            self.assertEqual(len(rows),2)
            self.assertEqual(rows[1][6],'Teste B');self.assertEqual(rows[1][7],'2')
            self.assertEqual(rows[1][9],'Execução no Brasil não comprovada')
            self.assertEqual(list(book['Resumo por motivo'].values)[1],('Execução no Brasil não comprovada',1))
        self.assertEqual(db.read_bytes(),before)
        self.add('4')
        with self.assertRaises(ValueError):holiday_review.pending_excel(db,revision,'2026-09')

    def test_exclusion_restoration_cache_and_closed_snapshot(self):
        a=self.add('1',city='Desconhecido');self.add('2')
        def summary():return cached_queries.holiday_pending_summary(str(storage.DATA),queries.revision(),'2026-09',None,None)
        initial=self.totals();self.assertEqual(summary()[0]['Quantidade'],1)
        storage.set_import_deleted('2026-09',a,True,'teste')
        self.assertEqual(summary(),[])
        storage.set_import_deleted('2026-09',a,False,'teste')
        self.assertEqual(summary()[0]['Quantidade'],1);self.assertEqual(self.totals(),initial)
        storage.close_month('2026-09')
        before=self.totals();pending=holiday_review.page('2026-09',situation='Pendências')
        holidays.bind('Desconhecido','Agudos','SP')
        self.assertEqual(holiday_review.page('2026-09',situation='Pendências'),pending)
        self.assertEqual(sum(r['Quantidade'] for r in summary()),before[1]['holiday_pending'])
        self.assertEqual(holiday_review.page('2026-09',situation='Elegíveis cobrados')[0],before[1]['holiday_quantity'])
        self.assertEqual(self.totals(),before)

    def test_state_municipal_pending_and_closed_divergence_preserve_old_counters(self):
        holidays.delete(holidays.calendar()[0]['id'])
        holidays.save('2026-09-07','Teste','Municipal','SP','Agudos')
        self.add('1',city='Desconhecido')
        self.assertEqual(holiday_review.pending_summary('2026-09')[0]['Motivo'],'Município/UF não confirmado')
        holidays.delete(holidays.calendar()[0]['id']);holidays.save('2026-09-07','Teste','Estadual','SP')
        self.assertEqual(holiday_review.pending_summary('2026-09')[0]['Motivo'],'UF não confirmada')
        self.add('2');self.add('2',city='ATC ARACARIGUAMA',note='divergente')
        # Freeze directly to exercise existing divergent snapshots (normal closing blocks business duplicates).
        with storage.connect() as c:holidays.freeze(c,'2026-09',True)
        before=self.totals()
        self.assertEqual(sum(r['Quantidade'] for r in holiday_review.pending_summary('2026-09')),before[1]['holiday_pending'])
        self.assertEqual(holiday_review.page('2026-09',situation='Não cobrados')[0],3)
        self.assertEqual(self.totals(),before)

    def test_interface_situation_and_summary(self):
        self.add('1',city='Desconhecido');self.add('2')
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
        app.sidebar.date_input[0].set_value(date(2026,9,1)).run()
        navigate(app,'Fechamento mensal')
        self.assertFalse(app.exception)
        situation=next(s for s in app.selectbox if s.label=='Situação')
        self.assertEqual(tuple(situation.options),holiday_review.SITUATIONS)
        before=self.totals()
        for option in holiday_review.SITUATIONS:
            next(s for s in app.selectbox if s.label=='Situação').set_value(option).run()
            self.assertFalse(app.exception)
        self.assertEqual(self.totals(),before)
