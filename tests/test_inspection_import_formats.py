"""Compatibilidade dos modelos originais: testes só em bancos temporários."""
from io import BytesIO
from datetime import datetime
from pathlib import Path
import hashlib,json,tempfile,unittest
import openpyxl
import inspections as op
import inspection_billing as billing

class ImportFormats(unittest.TestCase):
 def workbook(self,headers,rows,title='Execução'):
  w=openpyxl.Workbook();w.active.title=title;w.active.append(headers)
  for row in rows:w.active.append(row)
  b=BytesIO();w.save(b);w.close();return b.getvalue()
 def modern(self,n=1):
  headers=['Descrição TSS','Data Fim Execução','Município','Número OS','Status da Operação','Código TSS','Data Início Execução','Status da OS']+[f'Campo extra {i}' for i in range(29)]
  rows=[['EXAME PREDIAL ALTA DE CONSUMO COMP MD',datetime(2026,10,2,10),'AGUDOS',str(i),'Fechada',123,datetime(2026,10,2,9),'Fechada']+list(range(29)) for i in range(n)]
  return self.workbook(headers,rows)
 def test_execution_4448_rows_37_columns_preview_and_import(self):
  content=self.modern(4448);sha=hashlib.sha256(content).hexdigest()
  self.assertEqual(op.sheets(content),['Execução']);p=op.preview(content,'Execução')
  self.assertEqual((p['records'],p['months'],p['missing_deadline'],p['invalid_execution']),(4448,{'2026-10':4448},4448,0))
  self.assertEqual(p['fields']['TSS'],'Descrição TSS')
  self.assertNotIn('Prazo de Execução - Início',p['fields'])
  with tempfile.TemporaryDirectory() as root:
   self.assertEqual(op.import_file(root,content,'outubro.xlsx','Execução'),4448)
   with op.connect(root) as c:
    r=c.execute('SELECT * FROM visits ORDER BY id LIMIT 1').fetchone();raw=json.loads(r['raw'])
    self.assertEqual(r['day'],'2026-10-02');self.assertEqual(r['status'],'Pendente de data')
    self.assertEqual(raw['Descrição TSS'],raw['TSS']);self.assertEqual(raw['Campo extra 28'],28)
   self.assertEqual((Path(root)/'originais'/(sha+'.xlsx')).read_bytes(),content)
   with self.assertRaisesRegex(ValueError,'já possui'):op.import_file(root,content,'renomeado.xlsx','Execução')
   total,_,pending=op.summary(root,'2026-10-01','2026-10-31')
   self.assertEqual(total['total'],0);self.assertEqual(pending,4448)
   billing.sync(root);p=billing.preview(root,'2026-10')
   self.assertEqual(p['inspection_cents'],4448*2250)
  self.assertEqual(hashlib.sha256(content).hexdigest(),sha)
 def test_previous_format_reordered_headers_identical_financial_and_deadline(self):
  raw={'Número OS':'1','Município':'AGUDOS','Status da OS':'Fechada','Status da Operação':'Fechada','Prazo de Execução - Início':'01/09/2026 00:00','Prazo de Execução - Fim':'02/09/2026 10:00','Data Fim Execução':'02/09/2026 10:00','TSS':'EXAME PREDIAL ALTA DE CONSUMO COMP MD'}
  totals=[]
  for headers in [list(op.HEADERS),list(reversed(op.HEADERS))]:
   content=self.workbook(headers,[[raw[k] for k in headers]],'Número OS')
   with tempfile.TemporaryDirectory() as root:
    self.assertEqual(op.sheets(content),['Número OS']);self.assertEqual(op.preview(content,'Número OS')['missing_deadline'],0)
    op.import_file(root,content,'setembro.xlsx','Número OS');billing.sync(root)
    totals.append((billing.preview(root,'2026-09')['inspection_cents'],op.summary(root,'2026-09-01','2026-09-30')[0]['inside']))
  self.assertEqual(totals,[(2250,1),(2250,1)])
 def test_preview_missing_data_and_ambiguous_headers(self):
  headers=['Número OS','Município','Status da OS','Status da Operação','Data Fim Execução','Descrição TSS']
  content=self.workbook(headers,[['1','AGUDOS','Fechada','Fechada','inválida',''],[None]*6])
  p=op.preview(content,'Execução');self.assertEqual(p['records'],1);self.assertEqual(p['months'],{});self.assertEqual(p['invalid_execution'],1);self.assertEqual(p['missing_tss'],1)
  for bad in [headers+['TSS'],headers[:-1]]:
   content=self.workbook(bad,[]);self.assertEqual(op.sheets(content),[])
   with self.assertRaises(ValueError):op.preview(content,'Execução')
 def test_october_does_not_modify_september_and_approved_month_is_blocked(self):
  import sqlite3
  with tempfile.TemporaryDirectory() as root:
   content=self.workbook(op.HEADERS,[['sep','AGUDOS','Fechada','Fechada','','','02/09/2026 10:00','VISTORIA']], 'Número OS')
   op.import_file(root,content,'setembro.xlsx','Número OS')
   with op.connect(root) as c:before=[tuple(r) for r in c.execute('SELECT * FROM visits')]
   op.import_file(root,self.modern(),'outubro.xlsx','Execução')
   with op.connect(root) as c:self.assertEqual([tuple(r) for r in c.execute('SELECT * FROM visits WHERE import_id=1')],before)
   with sqlite3.connect(Path(root)/'financeiro.sqlite3') as c:
    c.execute('CREATE TABLE approvals(month TEXT)');c.execute("INSERT INTO approvals VALUES('2026-10')")
   with self.assertRaisesRegex(ValueError,'já aprovada'):op.import_file(root,self.modern(2),'outubro2.xlsx','Execução')
   with op.connect(root) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM imports').fetchone()[0],2)
 def test_incorrect_a1_dimensions_do_not_truncate_records(self):
  from zipfile import ZipFile,ZIP_DEFLATED
  import re
  original=self.modern(3);b=BytesIO()
  with ZipFile(BytesIO(original)) as source,ZipFile(b,'w',ZIP_DEFLATED) as target:
   for item in source.infolist():
    payload=source.read(item.filename)
    if item.filename=='xl/worksheets/sheet1.xml':payload=re.sub(rb'<dimension ref="[^"]+"',b'<dimension ref="A1"',payload)
    target.writestr(item,payload)
  content=b.getvalue();self.assertEqual(op.sheets(content),['Execução']);self.assertEqual(op.preview(content,'Execução')['records'],3)
  with tempfile.TemporaryDirectory() as root:
   self.assertEqual(op.import_file(root,content,'export.xlsx','Execução'),3)
   with op.connect(root) as c:
    self.assertEqual(c.execute('SELECT COUNT(*) FROM visits').fetchone()[0],3)
    self.assertEqual(json.loads(c.execute('SELECT raw FROM visits LIMIT 1').fetchone()[0])['Campo extra 28'],28)
