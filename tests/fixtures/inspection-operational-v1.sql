-- Base sintética produzida pelo commit 568bc75. Nenhum dado de produção.
BEGIN TRANSACTION;
CREATE TABLE imports(id INTEGER PRIMARY KEY,sha TEXT NOT NULL,sheet TEXT NOT NULL,name TEXT NOT NULL,created TEXT NOT NULL,UNIQUE(sha,sheet));
INSERT INTO "imports" VALUES(1,'test','Número OS','teste.xlsx','2026-09-01');
CREATE TABLE penalties(id INTEGER PRIMARY KEY,created TEXT NOT NULL,payload TEXT NOT NULL);
CREATE TABLE visits(id INTEGER PRIMARY KEY,import_id INTEGER NOT NULL,line INTEGER NOT NULL,os TEXT,city TEXT,day TEXT,status TEXT NOT NULL,fingerprint TEXT NOT NULL UNIQUE,raw TEXT NOT NULL,UNIQUE(import_id,line));
INSERT INTO "visits" VALUES(1,1,2,'OS1','MACATUBA','2026-09-01','Dentro do prazo','fingerprint','{"TSS": "VISTORIA CADASTRAL", "Contrato": "C1", "Status da OS": "Fechada", "Status da Opera\u00e7\u00e3o": "Fechada", "Data Fim Execu\u00e7\u00e3o": "01/09/2026 10:00"}');
CREATE INDEX visit_period ON visits(day,status,city);
COMMIT;
PRAGMA user_version=1;
