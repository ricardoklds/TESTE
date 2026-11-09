"""Correção somente leitura da conferência congelada, sem editar os snapshots."""
import localities

FIELDS=('id','day','employee','city','group_name','supply','execution','municipality','state','country','location_evidence','status')


def frozen_candidates_sql(month,start=None,end=None):
    confirmations=localities.municipal_confirmations()
    values=','.join('(?,?,?,?)' for _ in confirmations) or "('','','','')"
    args=[month];period=''
    if start is not None:period=" AND json_extract(f.detail,'$.day') BETWEEN ? AND ?";args.extend([start,end])
    stored='SELECT '+','.join(f"json_extract(f.detail,'$.{k}') AS {k}" for k in FIELDS)
    stored+=',p.source FROM holiday_frozen_review f LEFT JOIN holiday_identity_records p ON p.id=f.id WHERE f.month=?'+period
    context="""EXISTS(SELECT 1 FROM holidays h WHERE h.day=s.day AND h.scope='Municipal')
        AND NOT EXISTS(SELECT 1 FROM holidays h WHERE h.day=s.day AND h.scope IN ('Nacional','Estadual'))"""
    difference="""s.status IN ('Município/UF não confirmado','Não aplicável','Não aplicável — outro município')
        AND EXISTS(SELECT 1 FROM holidays h WHERE h.day=s.day AND h.scope='Municipal')
        AND NOT EXISTS(SELECT 1 FROM holidays h WHERE h.day=s.day AND h.scope='Municipal'
          AND (s.resolved_state='' OR h.state=s.resolved_state)
          AND (s.resolved_municipality='' OR h.municipality=s.resolved_municipality))"""
    sql='WITH confirmations(source,municipality,state,evidence) AS (VALUES '+values+'''),
        stored AS ('''+stored+'''), resolved AS (
          SELECT s.*,COALESCE(NULLIF(s.municipality,''),NULLIF(k.municipality,''),'') resolved_municipality,
            COALESCE(NULLIF(s.state,''),NULLIF(k.state,''),'') resolved_state,k.evidence confirmed_evidence
          FROM stored s LEFT JOIN confirmations k ON k.source=s.source AND '''+context+'''
        ), classified AS (SELECT s.*,CASE WHEN '''+difference+''' THEN 1 ELSE 0 END other_municipality FROM resolved s)
        SELECT '''+','.join(
            "CASE WHEN other_municipality=1 THEN 'Não aplicável — outro município' ELSE status END status" if k=='status' else
            'CASE WHEN other_municipality=1 THEN resolved_municipality ELSE municipality END municipality' if k=='municipality' else
            'CASE WHEN other_municipality=1 THEN resolved_state ELSE state END state' if k=='state' else
            'CASE WHEN other_municipality=1 AND confirmed_evidence IS NOT NULL THEN confirmed_evidence ELSE location_evidence END location_evidence' if k=='location_evidence' else k
            for k in FIELDS)+' FROM classified'
    return sql,[*[v for row in confirmations for v in row],*args]
