# Conferência do adicional de feriado

Na tela **Fechamento mensal → Conferência do adicional de feriado**, o filtro
**Situação** oferece:

- **Todos:** todos os registros do universo de conferência já usado pelo sistema.
- **Elegíveis cobrados:** somente os IDs efetivamente selecionados pela consulta de
  cobrança existente; um filtro de funcionário/município não transfere a cobrança
  de uma execução duplicada para outra linha.
- **Pendências:** os motivos já contabilizados pelo indicador de pendências.
- **Não cobrados:** registros dessa conferência sem adicional, incluindo pendências
  e duplicatas sem cobrança. Não significa todos os registros de leitura do contrato;
  o universo de candidatos e a exclusão de “Não aplicável” permanecem iguais.

O resumo mostra quantos registros pendentes há por motivo, respeitando período,
município, grupo e funcionário. Ele independe da situação selecionada: mesmo ao
visualizar cobrados, o resumo continua sendo das pendências nos demais filtros.
Os motivos incluem execução no Brasil não comprovada, UF não confirmada,
município/UF não confirmado, fornecimento/execução ausente, domingo e localidades
divergentes na mesma execução. Não há confirmação ou resolução automática.

**Exportar pendências para Excel** gera, em segundo plano, todas as pendências desses
filtros, inclusive as que estão em outras páginas. Ao terminar, clique em
**Preparar download das pendências → Baixar pendências em Excel**. As abas contêm:

- ID, data, município, UF, Cidade/ATC original da conferência, grupo, funcionário,
  fornecimento, execução, motivo, país e comprovação da localidade.
- Resumo por motivo e filtros/revisão usados na exportação.

O arquivo é invalidado na interface se a revisão da base ou os filtros mudarem.
Textos são exportados como texto, sem executar fórmulas. Acima do limite do Excel,
as linhas são divididas automaticamente em abas, sem descartar registros.

## Preservação dos cálculos e meses fechados

Não foram modificados `core.py`, `holidays.py`, preços, critérios, regras de localidade,
projeções, schema, importações ou registros originais. O módulo novo só faz SELECT.
Os IDs cobrados vêm da consulta original, inclusive dos snapshots de meses fechados.
Não há migração nem necessidade de reimportar ou reabrir um mês para usar os filtros.

Meses fechados mantêm a classificação de pendência usada pelo indicador existente.
Em snapshots antigos, execuções elegíveis sem cobrança por divergência podem constar
em **Não cobrados**, sem passar a incrementar automaticamente as pendências do mês
fechado. A tela mostra o motivo, mas não muda esse histórico nem a cobrança.

Os valores **19.951 cobrados e 834 pendências em setembro/2026** foram informados pelo
usuário. Essa base não está disponível neste ambiente: não se afirma ter reproduzido
esses números. A atualização deixa intactos os cálculos que os produzem. Ao atualizar
na instalação que contém setembro, confira os indicadores no mês completo e sem
filtros adicionais; a soma do resumo de pendências deve acompanhar esse indicador.

Correção posterior: o usuário identificou as 834 pendências como ATC BOCAINA e confirmou
Bocaina/SP. A classificação municipal agora distingue **Não aplicável — outro município**.
Consulte [BOCAINA_CORRECTION.md](BOCAINA_CORRECTION.md): a correção pode reduzir o
indicador de pendências, inclusive por projeção de meses fechados, mantendo os valores,
IDs cobrados e snapshots gravados. Os números acima são o relato anterior à correção.

## Desempenho e consistência

O SQL aplica situação/localidade/período antes de LIMIT/OFFSET. O Python recebe no
máximo 100 linhas por página na interface (API limitada a 500), mais poucos grupos
agregados de motivo. Não há leitura de planilhas nem carregamento de todos os registros
para filtrá-los. As consultas reutilizam os candidatos da cobrança existente via CTE
materializada. Contagens por motivo são compartilhadas entre situações/páginas por
cache com chave de revisão, mês, período e filtros; alterações já auditadas invalidam
esse cache. Não foram adicionados índices ou tabelas.

O Excel usa cursor SQL, uma transação de leitura consistente e escrita incremental.
Não copia o banco inteiro. Durante a geração, o SQLite pode adiar uma escrita
concorrente até terminar essa leitura. Gere exportações extensas fora da importação;
o trabalho fica em segundo plano e não mantém os registros em memória Python.
O download preparado pelo Streamlit pode usar memória proporcional ao arquivo final.

`benchmark_holiday_review.py` cria um milhão de registros sintéticos em banco
temporário por SQL, com um mês/30 dias. Mede exclusivamente as consultas da nova
conferência, não importação de Excel, navegador, dados reais ou anos de concorrência.
Os dados e projeções desse ensaio são artificiais e removidos ao finalizar.

```bash
.venv/bin/python benchmark_holiday_review.py --output /tmp/holiday-review-million.json
```

Evidências medidas e saída dos testes ficam em `measurements/holiday-review/`.

Medições em 14/10/2026, no ambiente Linux de testes, um milhão de linhas sintéticas:

| Operação | Tempo medido |
| --- | ---: |
| Todos — primeira consulta da interface | 3,566 s |
| Elegíveis cobrados — contagens já em cache | 1,711 s |
| Pendências — contagens já em cache | 1,808 s |
| Não cobrados — contagens já em cache | 1,731 s |
| Resumo por motivo — grupos já em cache | 0,000584 s |
| Mesma página de pendências novamente — cache completo | 0,000280 s |

Sem esse cache, as chamadas diretas de contagem + página ficaram entre 3,43 e
3,60 s. Cada página retornou somente 100 registros. O resumo direto levou 1,798 s.
São tempos efetivamente medidos de uma execução, sem navegador e sem garantia para
outro computador. A criação da fixture SQL fica fora dos tempos; não é medição de
importação nem substitui os testes de Excel da entrega anterior.

**53 testes passaram.** Conferiram filtros, paginação, resumo, exportação, cache,
fechamentos congelados, exclusão/restauração e as regressões das seis regras.
`integrity_check` retornou `ok` no ensaio de carga e os totais financeiros não mudaram.
Os hashes dos sete arquivos de produção (banco, originais e backups presentes neste
ambiente) permaneceram iguais.

## Atualizar no Windows

1. Feche o Streamlit. Faça uma cópia externa da pasta `data` inteira e do programa
   anterior, conforme [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md).
2. Extraia a entrega em uma pasta temporária. Copie o programa atualizado, incluindo
   **holiday_review.py**, **app.py**, **cached_queries.py**, `tests/`, documentação e
   os demais arquivos de código. Preserve `data/`, originais, backups e `.venv/`.
3. As dependências não mudaram. Sem reinstalar Python, no PowerShell da instalação:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_holiday_review.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_holidays.py -v
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1
```

Abra `http://localhost:8501`, selecione setembro/2026, mês completo, e entre em
**Fechamento mensal**. Compare os indicadores anteriores, selecione **Pendências**,
confira os motivos e exporte. Nenhum servidor foi publicado na internet.
