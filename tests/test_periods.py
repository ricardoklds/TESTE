"""Fixtures isoladas de regressão: nunca são importadas no banco do usuário."""
import copy
from datetime import date, datetime
import unittest
import core
import periods
import storage
from exports import productivity


def fixture(number, value, *, excluded=False, errors=None, key=None):
    return {'id':number, 'import_id':1, 'excluded':excluded,
            'raw':{'Data da Leitura Atual':value},
            'result':{'errors':errors or [], 'key':key or str(number),
                      'employee':'Fixture de teste', 'city':'Fixture de teste',
                      'units':{'138':1,'128':0,'137':0,'impressao':2,'apontamento':1}}}


class PeriodTests(unittest.TestCase):
    def setUp(self):
        self.mapping={1:{'date':'Data da Leitura Atual'}}
        self.rows=[fixture(1,'01/10/2026'),fixture(2,'10/10/2026'),
                   fixture(3,'2026-10-31T23:59:59'),fixture(4,''),
                   fixture(5,'31/02/2026'),fixture(6,'30/09/2026'),
                   fixture(7,'10/10/2026',excluded=True),
                   fixture(8,'10/10/2026',errors=['Erro de origem'])]

    def select(self,start,end):
        return periods.filter_period(self.rows,self.mapping,'2026-10',start,end)

    def test_day(self):
        selected=self.select(date(2026,10,10),date(2026,10,10))
        self.assertEqual([r['id'] for r in selected],[2,7,8])
        self.assertEqual([r['id'] for r in periods.valid_records(selected)],[2])

    def test_inclusive_interval(self):
        self.assertEqual([r['id'] for r in self.select(date(2026,10,1),date(2026,10,10))],[1,2,7,8])

    def test_month_and_missing_invalid_dates(self):
        start,end=periods.month_bounds('2026-10')
        self.assertEqual([r['id'] for r in self.select(start,end)],[1,2,3,7,8])
        self.assertEqual([r['id'] for r in periods.valid_records(self.select(start,end))],[1,2,3])

    def test_empty_period(self):
        self.assertEqual(self.select(date(2026,10,12),date(2026,10,12)),[])
        prices={k:v[2] for k,v in core.CATEGORIES.items()}
        self.assertEqual(sum(r['total_cents'] for r in core.summarize([],prices)),0)

    def test_reversed_period(self):
        with self.assertRaisesRegex(ValueError,'inicial'):
            self.select(date(2026,10,20),date(2026,10,10))

    def test_outside_reference_month(self):
        with self.assertRaisesRegex(ValueError,'mês'):
            self.select(date(2026,9,30),date(2026,10,10))

    def test_leap_and_year_boundaries(self):
        self.assertEqual(periods.month_bounds('2024-02')[1],date(2024,2,29))
        self.assertEqual(periods.month_bounds('2025-02')[1],date(2025,2,28))
        self.assertEqual(periods.month_bounds('2026-12')[1],date(2026,12,31))

    def test_mapping_and_typed_dates(self):
        row=fixture(1,'10/10/2026');row['raw']={'Data personalizada':datetime(2026,10,10,23,59)}
        self.assertEqual(periods.record_date(row,{1:{'date':'Data personalizada'}}),date(2026,10,10))
        self.assertIsNone(periods.record_date(row,{1:{'date':None}}))
        self.assertEqual(periods.parse_date(date(2026,10,10)),date(2026,10,10))
        self.assertIsNone(periods.parse_date(46305))

    def test_filter_does_not_mutate_or_recalculate(self):
        before=copy.deepcopy(self.rows)
        for _ in range(3):self.select(date(2026,10,10),date(2026,10,10))
        self.assertEqual(self.rows,before)

    def test_duplicates_are_identified_over_whole_month(self):
        self.rows[0]['result']['key']=self.rows[1]['result']['key']='chave repetida'
        groups=storage.conflicts(self.rows)
        selected=self.select(date(2026,10,10),date(2026,10,10))
        self.assertEqual(periods.visible_conflicts(groups,selected),[[1,2]])
        self.assertEqual(periods.visible_conflicts(groups,[]),[])

    def test_quantities_values_and_productivity_use_same_valid_rows(self):
        valid=periods.valid_records(self.select(date(2026,10,10),date(2026,10,10)))
        prices={k:v[2] for k,v in core.CATEGORIES.items()}
        summary=core.summarize(valid,prices)
        self.assertEqual(sum(r['total_cents'] for r in summary),288)
        self.assertEqual({r['key']:r['Quantidade'] for r in summary},
                         {'138':1,'128':0,'137':0,'impressao':2,'apontamento':1})
        for by in ('employee','city'):
            self.assertEqual(sum(r['total_cents'] for r in productivity(valid,prices,by)),288)

    def test_rankings_change_with_period(self):
        self.rows[0]['result']['employee']='Fixture A'
        self.rows[1]['result']['employee']='Fixture B'
        self.rows[2]['result']['employee']='Fixture A'
        prices={k:v[2] for k,v in core.CATEGORIES.items()}
        first,last=periods.month_bounds('2026-10')
        monthly=productivity(periods.valid_records(self.select(first,last)),prices,'employee')
        daily=productivity(periods.valid_records(self.select(date(2026,10,10),date(2026,10,10))),prices,'employee')
        self.assertEqual(monthly[0]['Funcionário'],'Fixture A')
        self.assertEqual(monthly[0]['Leituras faturáveis'],2)
        self.assertEqual(daily[0]['Funcionário'],'Fixture B')
        self.assertEqual(len(daily),1)


if __name__=='__main__':unittest.main()
