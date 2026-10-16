from ui_navigation import navigate
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO
import openpyxl
import core,storage,queries,periods,excel_io,fast_reports,cached_queries

SOURCE=storage.DATA/'contrato.sqlite3'

@unittest.skipUnless(SOURCE.exists(),'Requer base real importada')
class PerformanceQueries(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=storage.DATA;storage.DATA=Path(self.temp.name)
        with sqlite3.connect(SOURCE) as src,sqlite3.connect(storage.DATA/'contrato.sqlite3') as dst:src.backup(dst)

    def tearDown(self):
        storage.DATA=self.old;self.temp.cleanup()

    def test_sql_matches_saved_financial_rules_and_periods(self):
        month='2026-10';rows=storage.records(month);prices=storage.month_info(month)['prices']
        self.assertEqual(queries.summary(queries.overview(month),prices),core.summarize(rows,prices))
        maps=periods.import_mappings(storage.imports(month))
        for start,end in [('2026-10-01','2026-10-31'),('2026-10-10','2026-10-10'),('2026-10-11','2026-10-11')]:
            subset=periods.valid_records(periods.filter_period(rows,maps,month,periods.parse_date(start),periods.parse_date(end)))
            self.assertEqual(queries.summary(queries.overview(month,start,end),prices),core.summarize(subset,prices))
            for by in ('employee','city','group'):
                from exports import productivity
                actual=queries.productivity(month,prices,by,start,end);expected=productivity(subset,prices,by)
                self.assertEqual({next(iter(r.values())):r for r in actual},{next(iter(r.values())):r for r in expected})
        with storage.connect() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM records').fetchone()[0],c.execute('SELECT COUNT(*) FROM record_metrics').fetchone()[0])

    def test_pagination_bounded_and_row_exact(self):
        count,first=queries.record_page('2026-10',limit=100)
        _,second=queries.record_page('2026-10',offset=100,limit=100)
        self.assertEqual(count,19668);self.assertEqual(len(first),100)
        self.assertFalse({r['id'] for r in first}&{r['id'] for r in second})
        self.assertEqual(first[0],storage.records('2026-10')[0])

    def test_cache_revision_invalidation_for_all_mutations(self):
        month='2026-10';path=str(storage.DATA);revision=queries.revision()
        initial=cached_queries.overview(path,revision,month)
        entry=storage.imports(month)[0]
        storage.set_import_deleted(month,entry['id'],True,'Teste de invalidação')
        new=queries.revision();self.assertGreater(new,revision)
        self.assertEqual(cached_queries.overview(path,new,month)['active_count'],0)
        storage.set_import_deleted(month,entry['id'],False,'Restaurar teste')
        self.assertEqual(cached_queries.overview(path,queries.revision(),month),initial)
        row=queries.record_page(month,limit=1)[1][0]
        storage.exclude(month,row['id'],'Teste individual')
        self.assertGreater(queries.revision(),new)
        self.assertEqual(queries.overview(month)['active_count'],19667)
        revision=queries.revision();storage.save_setting('contract',{'name':'Teste de configuração'})
        self.assertGreater(queries.revision(),revision)
        revision=queries.revision();storage.update_month_prices(month,storage.month_info(month)['prices'])
        self.assertGreater(queries.revision(),revision)

    def test_fast_reports_and_streaming_details_have_same_total(self):
        month='2026-10';prices=storage.month_info(month)['prices'];stats=queries.overview(month)
        summary=queries.summary(stats,prices);products={by:queries.productivity(month,prices,by) for by in ('employee','city','group')}
        args=(month,summary,products,storage.imports(month),storage.audit(month),{},False,{})
        short=fast_reports.summary_excel(*args)
        book=openpyxl.load_workbook(BytesIO(short),read_only=True,data_only=True)
        self.assertEqual(round(book['Fechamento']['E11'].value*100),3045412);book.close()
        full=fast_reports.detailed_excel(str(storage.DATA/'contrato.sqlite3'),queries.revision(),month,prices,args)
        book=openpyxl.load_workbook(full,read_only=True,data_only=True)
        raw=book['Dados importados'];self.assertEqual(sum(1 for _ in raw),19669)
        self.assertEqual(round(book['Fechamento']['E11'].value*100),3045412);book.close()

    def test_preview_small_and_stream_rollback_on_failure(self):
        original=next((SOURCE.parent/'originais').glob('*.xlsx')).read_bytes()
        preview=excel_io.inspect(original)[0];self.assertLessEqual(len(preview['records']),15)
        from itertools import islice
        streamed=list(islice(excel_io.iter_records(original,preview),15))
        self.assertEqual(streamed,preview['records'])
        before=queries.revision();count=queries.overview('2026-11')['total_records']
        def broken():
            yield from islice(excel_io.iter_records(original,preview),1001)
            raise ValueError('Falha simulada de leitura')
        with self.assertRaises(ValueError):storage.import_sheet(original,'teste.xlsx',{**preview,'records':broken()},preview['mapping'],'2026-11')
        self.assertEqual(queries.overview('2026-11')['total_records'],count);self.assertEqual(queries.revision(),before)

    def test_no_complete_record_read_during_navigation(self):
        from streamlit.testing.v1 import AppTest
        with patch.object(storage,'records',side_effect=AssertionError('Leitura completa proibida na navegação')):
            at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
            for page in ('Painel inicial','Importar planilhas','Fechamento mensal','Produtividade','Relatórios'):
                navigate(at,page)
                self.assertFalse(at.exception,page)

    def test_background_export_allows_navigation(self):
        import threading
        from streamlit.testing.v1 import AppTest
        gate=threading.Event();started=threading.Event()
        def worker(*args):
            started.set();gate.wait(10)
        with patch.object(fast_reports,'detailed_excel',side_effect=worker):
            at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
            navigate(at,'Relatórios')
            next(b for b in at.button if b.label=='Gerar Excel completo em segundo plano').click().run()
            try:
                self.assertTrue(started.wait(2));self.assertFalse(at.exception)
                navigate(at,'Painel inicial')
                self.assertFalse(at.exception)
                self.assertFalse(gate.is_set())
            finally:gate.set()
