# Reconciliação do painel e da auditoria — setembro/2026

## Causa comprovada no código e reproduzida

O Painel inicial, Fechamento mensal e Produtividade inicializavam as datas como primeiro e último dia do mês e enviavam esses limites ao SQL **mesmo em “Mês completo”**. Isso aplicava `day BETWEEN inicio AND fim` e `errors=0` às cinco categorias. A auditoria `auditoria_fechamento.py` e o acumulado mensal, por sua vez, somam as unidades já salvas dos registros ativos do mês de referência sem esse recorte de visualização. Registros sem data projetada (`day IS NULL`) ficam fora de `BETWEEN`, ainda que tenham unidades faturáveis pelas regras originais. Essa diferença de seleção foi reproduzida em testes e no grupo de outubro disponível neste ambiente.

A correção faz “Mês completo” enviar `None, None`, usando o mesmo acumulado que já existia, sem recalcular registros. Dia e intervalo personalizado continuam exigindo data válida no período. Um intervalo personalizado cobrindo todos os dias do mês continua sendo uma seleção por data, portanto pode diferir do acumulado. As legendas explicam a distinção. A mesma seleção vale para produtividade, conferência e suas consultas vinculadas.

Nenhuma regra, preço, cálculo salvo, calendário, correção de Bocaina ou arquivo original foi modificado. Não há migração de banco. Não foram adicionados filtros novos ou melhorias visuais.

## Resultados efetivamente medidos

Na base disponível aqui existe apenas outubro/2026, com 19.668 registros; setembro não está disponível.

| Verificação | Antes: antigo filtro de mês | Depois: acumulado mensal |
| --- | ---: | ---: |
| Grupo real de outubro disponível | R$ 30.410,24 | R$ 30.454,12 |
| Fixture sintética: leitura datada + leitura sem data | R$ 3,93 | R$ 6,81 |

Em outubro, a diferença de R$ 43,88 foi reconciliada integralmente a **44 registros com unidades faturáveis e sem data projetada**, dentre 46 registros com data projetada nula. As quantidades da diferença são: 2 leituras de R$ 1,38, 4 de R$ 1,28, 35 comunicados e 37 apontamentos; os outros dois serviços não têm diferença. Os dois registros restantes não contribuem financeiramente para a diferença. O Excel do diagnóstico contém os IDs e motivos, sem transformar uma ausência de data em uma data inventada.

Os testes de interface executam as três telas em fixture isolada, comparando o acumulado, o dia específico e Relatórios. Os testes também comparam a ferramenta de auditoria com as consultas SQL, preservam exclusão/restauração e o adicional congelado de mês fechado, e verificam que o banco permanece byte a byte idêntico após os diagnósticos. O resultado final da suíte está em `measurements/reconciliacao/regression-tests.txt`.

## Setembro: informado versus comprovado

Os valores informados mais recentemente são R$ 596.906,23 auditados, R$ 595.509,45 no painel anterior e 19.951 adicionais de feriado (R$ 20.948,55). A diferença aritmética é R$ 1.396,78:

| Categoria | Quantidade de diferença informada | Valor da diferença |
| --- | ---: | ---: |
| Leitura R$ 1,38 | 147 | R$ 202,86 |
| Leitura R$ 1,37 | 0 | R$ 0,00 |
| Leitura R$ 1,28 | 189 | R$ 241,92 |
| Adicional de feriado R$ 1,05 | 0 | R$ 0,00 |
| Adicional de impressão R$ 0,50 | 920 | R$ 460,00 |
| Apontamento operacional R$ 0,50 | 984 | R$ 492,00 |

Esta aritmética não identifica os registros. **Ainda não foi comprovado que os 1.606 registros sem data explicam a diferença de setembro**, nem se os dois resultados usam o mesmo estado da base. O valor não é imposto ao aplicativo. O diagnóstico abaixo faz a conciliação na base local, usando seus preços salvos e o calendário existente, inclusive os IDs congelados quando houver.

O quadro “Comparação” da auditoria anterior conserva os valores manuais históricos (19.955 feriados e R$ 596.910,43). Para a execução real, consulte `official_quantities` e `official_total_cents`, não confunda as referências históricas com resultados calculados. A nova ferramenta registra separadamente as referências mais recentes e os resultados atuais.

## Diagnóstico somente leitura no Windows

1. Feche o Streamlit e mantenha-o fechado durante o diagnóstico, para evitar alterações concorrentes e bloqueios da transação de leitura. Faça seu backup habitual da pasta `data` com o aplicativo fechado.
2. Atualize os arquivos do código pela branch `codex/sistema-fechamento-pr` ou pelo ZIP entregue. Preserve integralmente `data`, `.venv`, planilhas, relatórios anteriores e backups. Não substitua a pasta de instalação por uma pasta vazia. Não é necessário reinstalar Python ou dependências.
3. No terminal aberto na pasta do sistema, execute:

```powershell
.\.venv\Scripts\python.exe diagnostico_divergencia.py --data data --month 2026-09 --output reconciliacao-setembro-2026
```

A pasta de saída deve ser **nova e fora de `data`**; para repetir use outro nome. Se usa uma pasta de dados personalizada (`APP_DATA_DIR`), informe o caminho correto em `--data`. O diagnóstico não modifica o banco; recusa schema diferente da versão 5 e não executa migrações. Acesso SQLite é `mode=ro`, em uma única transação. Ele não chama `storage.connect()`, não reimporta e não abre as planilhas originais. Falha não significa conclusão: arquivos de saída parciais devem ser desconsiderados.

Serão gerados `reconciliacao.xlsx`, `resultado.json` e `RELATORIO.md`:

- **Comparação:** seis quantidades acumuladas versus o filtro antigo e diferenças em centavos.
- **Registros da diferença:** IDs, arquivo/linha, grupo, Cidade/ATC, funcionário, fornecimento, execução, data original/projetada, classe da data, erros, motivo e contribuição financeira individual. Registros sem contribuição para a diferença não entram nesta aba; a auditoria completa anterior permite conferir também esses registros.
- **Evidências:** mês disponível, revisão, mês fechado, hashes do código, preços implícitos na comparação e as validações.

Para comprovar os R$ 1.396,78, confira no JSON:

- `available: true`, `monthly_cents: 59690623`, `old_screen_cents: 59550945`, `delta_cents: 139678`;
- `matches_reported_totals`, `matches_reported_quantities`, `matches_reported_holidays`, `detail_matches_sql` e `audit_sql_matches_monthly` todos verdadeiros;
- os IDs e motivos na planilha, cuja soma precisa conciliar com o SQL. Um resultado diferente deve ser investigado, sem ajustar dados para alcançar a referência.

O SQL é agregado e usa os índices existentes por mês/data; detalhes são percorridos por cursor e exportados em modo incremental com divisão automática de abas no limite do Excel. Não carrega todos os registros em memória. A consulta de detalhe examina as projeções do mês, e une o JSON original apenas aos candidatos à diferença. Não foram medidos novos tempos em milhões de registros nesta alteração.

O diagnóstico ignora o cache do Streamlit para comparar o banco diretamente. Ele não consegue ler o cache da sessão que apresentou o problema no computador do usuário. A revisão do banco e os hashes registrados ajudam a comparar execuções. O defeito de seleção foi reproduzido sem cache; isso não comprova nem presume outro defeito de cache.

4. Depois da atualização, reinicie o aplicativo pelo seu iniciador habitual, ou:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

O reinício elimina o cache da sessão anterior. Escolha setembro/2026 e **Mês completo** nas três telas. Compare com Relatórios e o diagnóstico da mesma base. Não haverá reimportação nem alteração automática de setembro. Para voltar à versão anterior, restaure somente os arquivos de código; não sobrescreva os dados com versões antigas.

Para executar a regressão focada (somente bancos temporários):

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_reconciliation.py -v
```
