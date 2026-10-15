"""Cenários artificiais isolados. Nenhum feriado é inserido em produção."""
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
import openpyxl
import core,storage,holidays,queries,cached_queries,fast_reports

class HolidayTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.old=storage.DATA;storage.DATA=Path(self.temp.name)
        self.rows=[]

    def tearDown(self):
        storage.DATA=self.old;self.temp.cleanup()

    def add(self,day='12/10/2026',city='Origem A',printed='Sim',retained='Não',cause='',supply='TESTE-1',task='EXECUCAO-1',note='',month='2026-10'):
        raw={v:'' for v in core.FIELDS.values()}
        raw.update({'Data da Leitura Atual':day,'ATC':city,'Faturas Impressas':printed,'Fatura Retida':retained,
                    'Causas de Leitura/Não Leitura Atual':cause,'Quantidade comunicados impressos':2,'CO1 Atual':'Teste',
                    'Codigo do Fornecimento':supply,'Tarefa':task,'Nome do TACE':'Funcionário de teste','Grupo':'Grupo de teste','Observação de teste':note})
        w=openpyxl.Workbook();s=w.active;s.append(list(raw));s.append(list(raw.values()));out=BytesIO();w.save(out)
        p=core.parse_excel(out.getvalue())[0];storage.import_sheet(out.getvalue(),'fixture.xlsx',p,p['mapping'],month)
        return storage.imports(month)[-1]['id']

    def qty(self):return holidays.overview('2026-10')['holiday_quantity']

    def national(self):holidays.save('2026-10-12','Feriado de teste','Nacional')

    def test_national_state_and_municipal(self):
        self.add();self.add(city='Origem B',supply='TESTE-2')
        holidays.bind('Origem A','Cidade A','SP');holidays.bind('Origem B','Cidade B','RJ')
        for scope,state,town,expected in [('Nacional','','',2),('Estadual','SP','',1),('Municipal','RJ','Cidade B',1),('Municipal','SP','Cidade B',0)]:
            holidays.save('2026-10-12','Teste',scope,state,town);self.assertEqual(self.qty(),expected)
            holidays.delete(holidays.calendar()[0]['id'])

    def test_no_print_filter_and_five_rules_unchanged(self):
        for i,value in enumerate(['Sim','Não','','Valor não reconhecido']):self.add(printed=value,supply='TESTE-'+str(i))
        holidays.bind('Origem A','Cidade A','SP')
        prices=storage.month_info('2026-10')['prices'];before=core.summarize(storage.records('2026-10'),prices)
        self.national();self.assertEqual(self.qty(),4)
        self.assertEqual(queries.summary(queries.overview('2026-10'),prices),before)
        self.assertEqual(core.summarize(storage.records('2026-10'),prices),before)

    def test_exclusions_causes_missing_town_and_sunday(self):
        self.add(retained='Sim');self.add(cause='Imóvel fechado',supply='TESTE-2');self.add(supply='TESTE-3')
        self.national();self.assertEqual(self.qty(),0);self.assertEqual(holidays.overview('2026-10')['holiday_pending'],1)
        holidays.bind('Origem A','Cidade A','SP');self.assertEqual(self.qty(),1)
        self.add(day='11/10/2026',supply='TESTE-4');holidays.save('2026-10-11','Domingo de teste','Nacional')
        self.assertEqual(self.qty(),1);self.assertEqual(holidays.overview('2026-10')['holiday_pending'],1)
        self.assertTrue(any('Domingo' in r['status'] for r in holidays.page('2026-10')[1]))
        self.add(day='11/10/2026',supply='TESTE-5',retained='Sim')
        self.assertEqual(self.qty(),1);self.assertEqual(holidays.overview('2026-10')['holiday_pending'],2)

    def test_overlap_duplicate_execution_and_restore(self):
        a=self.add();b=self.add(note='Outra linha da mesma execução')
        holidays.bind('Origem A','Cidade A','SP');self.national()
        holidays.save('2026-10-12','Estadual sobreposto','Estadual','SP');holidays.save('2026-10-12','Municipal sobreposto','Municipal','SP','Cidade A')
        self.assertEqual(self.qty(),1)
        storage.set_import_deleted('2026-10',a,True,'Excluir duplicata de teste');self.assertEqual(self.qty(),1)
        storage.set_import_deleted('2026-10',b,True,'Excluir restante');self.assertEqual(self.qty(),0)
        storage.set_import_deleted('2026-10',a,False,'Restaurar');self.assertEqual(self.qty(),1)
        storage.set_import_deleted('2026-10',b,False,'Restaurar outra');self.assertEqual(self.qty(),1)

    def test_calendar_crud_uniqueness_and_closed_snapshot(self):
        self.add();holidays.bind('Origem A','Cidade A','SP');self.national()
        with self.assertRaises(ValueError):self.national()
        storage.close_month('2026-10');self.assertEqual(self.qty(),1)
        holidays.delete(holidays.calendar()[0]['id']);self.assertEqual(self.qty(),1)
        self.assertTrue(holidays.page('2026-10')[1][0]['Cobrado'])
        storage.close_month('2026-10',False,'Reabrir teste');self.assertEqual(self.qty(),0)
        self.national();h=holidays.calendar()[0]
        holidays.save('2026-10-13','Editar teste','Nacional',holiday_id=h['id']);self.assertEqual(self.qty(),0)

    def test_period_reports_and_cache(self):
        self.add();holidays.bind('Origem A','Cidade A','SP');self.national()
        self.assertEqual(holidays.overview('2026-10','2026-10-13','2026-10-13')['holiday_quantity'],0)
        prices=storage.month_info('2026-10')['prices'];path=str(storage.DATA)
        stats=cached_queries.overview(path,queries.revision(),'2026-10')
        summary=queries.summary(stats,prices);self.assertEqual(summary[-1]['total_cents'],105)
        self.assertEqual(holidays.page('2026-10',municipality='cidade a/SP')[0],1)
        self.assertEqual(holidays.page('2026-10',municipality='cidade b/SP')[0],0)
        self.assertEqual(holidays.page('2026-10',group='Grupo de teste',employee='Funcionário de teste')[0],1)
        products={by:cached_queries.productivity(path,queries.revision(),'2026-10',prices,by) for by in ('employee','city','group')}
        expected=sum(r['total_cents'] for r in summary)
        self.assertEqual(sum(r['total_cents'] for r in products['employee']),expected)
        args=('2026-10',summary,products,storage.imports('2026-10'),storage.audit('2026-10'),{},False,{})
        data=fast_reports.summary_excel(*args);book=openpyxl.load_workbook(BytesIO(data),data_only=True)
        self.assertEqual(round(book['Fechamento']['E12'].value*100),expected)
        revision=queries.revision();holidays.delete(holidays.calendar()[0]['id'])
        self.assertGreater(queries.revision(),revision)
        self.assertEqual(cached_queries.overview(path,queries.revision(),'2026-10')['holiday_quantity'],0)

    def test_closed_pending_is_preserved_and_municipality_conflict(self):
        self.add();self.national();storage.close_month('2026-10')
        self.assertEqual(holidays.overview('2026-10')['holiday_pending'],1)
        holidays.bind('Origem A','Cidade A','SP');self.assertEqual(self.qty(),0)
        self.assertEqual(holidays.overview('2026-10')['holiday_pending'],1)
        storage.close_month('2026-10',False,'Reabrir conferência')
        self.assertEqual(self.qty(),1)
        self.add(city='Origem B',note='Município divergente')
        holidays.bind('Origem B','Cidade B','RJ')
        self.assertEqual(self.qty(),0);self.assertEqual(holidays.overview('2026-10')['holiday_pending'],2)

    def test_calendar_and_locality_forms(self):
        from datetime import date
        from streamlit.testing.v1 import AppTest
        self.add()
        at=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=60).run()
        at.sidebar.selectbox[0].set_value('Configurações').run()
        self.assertFalse(at.exception)
        next(d for d in at.date_input if d.label=='Data do feriado').set_value(date(2026,10,12))
        next(t for t in at.text_input if t.label=='Descrição do feriado').set_value('Fixture UI')
        next(b for b in at.button if b.label=='Salvar feriado').click().run()
        self.assertFalse(at.exception);self.assertEqual(len(holidays.calendar()),1)
        next(t for t in at.text_input if t.label=='Município confirmado').set_value('Cidade A')
        next(t for t in at.text_input if t.label=='UF confirmada').set_value('SP')
        next(c for c in at.checkbox if c.label.startswith('Confirmo que esta origem')).check()
        next(b for b in at.button if b.label=='Salvar identificação municipal').click().run()
        self.assertFalse(at.exception);self.assertEqual(self.qty(),1)
        at.sidebar.selectbox[0].set_value('Leituras').run()
        at.sidebar.radio[0].set_value('Fechamento mensal').run()
        self.assertFalse(at.exception);self.assertEqual(at.metric[0].value,'R$ 3,93')
