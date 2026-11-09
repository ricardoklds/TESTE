"""Relatórios anuais sob demanda; consomem somente os 12 agregados da tela."""
from io import BytesIO
from contract_presentation import money

COLUMNS=[('month','Competência'),('readings_cents','Leituras'),('visits_cents','Vistorias'),('geo_cents','Geolocalização'),('gross_cents','Faturamento bruto'),('target_cents','Meta mensal'),('difference_cents','Diferença para a meta'),('achievement','Atingimento (%)'),('rolling_cents','Média móvel'),('status','Situação do fechamento'),('rolling_status','Situação da média móvel'),('notes','Observações')]

def indicators(report):
    current=report['current'];best=report['best'];worst=report['worst']
    return [('Acumulado disponível (inclui provisórios e parciais)',report['accumulated_cents']),('Acumulado aprovado',report['approved_cents']),('Acumulado provisório/parcial',report['provisional_cents']),('Média dos meses com composição completa (pode incluir provisórios)',report['average_cents']),('Melhor mês completo: '+(best['month'] if best else 'indisponível'),best['gross_cents'] if best else None),('Pior mês completo: '+(worst['month'] if worst else 'indisponível'),worst['gross_cents'] if worst else None),('Média móvel atual',current['rolling_cents'] if current else None),('Média móvel atual menos meta vigente',current['rolling_difference_cents'] if current else None),('Variação contra competência anterior',current['previous_difference_cents'] if current else None)]

def display(value,key):
    if value is None:return '—'
    if key.endswith('_cents'):return money(value)
    if key=='achievement':return f'{value:.2f}%'.replace('.',',')
    return str(value)

def excel(report):
    import openpyxl
    from openpyxl.styles import Font,PatternFill
    w=openpyxl.Workbook();s=w.active;s.title='Resumo anual';s.append(['Faturamento anual',report['year']]);s.append(['Média móvel (meses)',report['window']]);s.append(['Indicador','Valor (R$)'])
    for label,amount in indicators(report):
        s.append([label,amount/100 if amount is not None else None]);s.cell(s.max_row,2).number_format='"R$" #,##0.00'
    s.append(['Valores brutos: sem glosa. Ausência de dados não representa zero.']);s.append(['Completo = componentes disponíveis e sem pendências financeiras; não comprova todos os grupos importados.'])
    s=w.create_sheet('Competências');s.append([label for _,label in COLUMNS])
    for r in report['rows']:
        s.append([r[k]/100 if r[k] is not None and k.endswith('_cents') else r[k] for k,_ in COLUMNS])
        for j,(key,_) in enumerate(COLUMNS,1):
            if key.endswith('_cents'):s.cell(s.max_row,j).number_format='"R$" #,##0.00'
            if key=='achievement':s.cell(s.max_row,j).number_format='0.00"%"'
            if isinstance(s.cell(s.max_row,j).value,str):s.cell(s.max_row,j).data_type='s'
    s.freeze_panes='A2'
    for sheet in w:
        for c in sheet[1]:c.font=Font(bold=True,color='FFFFFF');c.fill=PatternFill('solid',fgColor='163A60')
        for c in sheet[1]:sheet.column_dimensions[c.column_letter].width=28 if sheet==s else 65
    b=BytesIO();w.save(b);return b.getvalue()

def pdf(report):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.pagesizes import landscape,A4
    from reportlab.lib import colors
    from xml.sax.saxutils import escape
    b=BytesIO();styles=getSampleStyleSheet();small=ParagraphStyle('annual',fontName='Helvetica',fontSize=7,leading=9)
    def p(value):return Paragraph(escape(str(value)),small)
    story=[Paragraph(f'Faturamento Anual — {report["year"]}',styles['Title']),p(f'Média móvel: {report["window"]} meses consecutivos. Valores brutos, sem glosa simulada.'),p('Valores provisórios/parciais não são fechamentos aprovados. Sem dados não significa zero.'),p('Composição completa: componentes disponíveis, sem pendências financeiras; não comprova cobertura de todos os grupos.'),Spacer(1,10)]
    for label,value in indicators(report):story.append(p(label+': '+(money(value) if value is not None else 'Indisponível')))
    story.append(Spacer(1,12));cols=COLUMNS[:10];data=[[p(label) for _,label in cols]]
    for r in report['rows']:data.append([p(display(r[key],key)) for key,_ in cols])
    table=Table(data,colWidths=[49,65,62,62,70,67,66,49,70,205-54],repeatRows=1)
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DCE9F5')),('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#163A60'))]));story.append(table)
    for r in report['rows']:
        if r['notes'] or r['rolling_status']!='Apenas aprovados':story.append(p(r['month']+': '+r['rolling_status']+'. '+r['notes']))
    SimpleDocTemplate(b,pagesize=landscape(A4),leftMargin=24,rightMargin=24,topMargin=24,bottomMargin=24).build(story);return b.getvalue()
