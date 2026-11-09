# Painel e relatórios gerenciais

## Alterações

O Painel inicial mostra três valores em centavos inteiros, formatados em reais: leituras e adicionais normais (as cinco categorias originais), adicional de feriados e faturamento total. A identidade `normais + feriados = total` é calculada sobre as quantidades existentes, sem refazer as regras financeiras.

Os filtros de **Cidade/ATC da origem**, grupo e funcionário aceitam várias seleções e podem ser combinados. Sem seleção significa **Todos**; o botão “Todos — limpar filtros gerenciais” restaura a seleção completa. As opções vêm da competência inteira. Ao escolher um período sem movimento para o funcionário selecionado, a seleção continua ativa e o resultado é zero; ela não se transforma silenciosamente em Todos.

Cidade/ATC é o texto disponível na origem. Não se transforma uma ATC em outro município nem se atribui uma localidade por aproximação. Campos vazios ou sem identificação aparecem na categoria “Não informado”, que participa das somas e filtros; o arquivo original não é preenchido com esse rótulo. A identificação municipal para elegibilidade dos feriados continua pertencendo ao módulo já validado e não foi alterada.

Por funcionário, o painel mostra registros processados, leituras faturáveis e faturamento, com normais e feriados separados. “Processados” significa registros ativos da seleção, inclusive os que têm erros; isso não os torna faturáveis. Os indicadores de leituras e valores mantêm as validações financeiras existentes. Os adicionais não são somados à quantidade de leituras como se fossem novas leituras.

O ranking exibe até 50 funcionários, ordenados por leituras faturáveis e nome em caso de empate, e um gráfico dos 15 maiores volumes. Os indicadores incluem todos os funcionários, mesmo quando o ranking é limitado. O detalhamento por cidade/ATC, grupo e funcionário tem páginas de até 100 combinações. O Excel gerencial inclui **todos** os agregados, inclusive as abas completas de funcionários, cidades e grupos. O PDF é um resumo identificado: indicadores, gráfico, até 50 funcionários e até 100 combinações da primeira página; ele não finge representar todos os detalhes quando há mais combinações.

## Períodos e fechamentos oficiais

- **Mês completo:** acumulado do mês de referência, incluindo os registros sem data que já participavam conforme as regras vigentes.
- **Dia específico / intervalo personalizado:** data de leitura inclusiva; registros sem data ficam fora dessa visualização e continuam no acumulado. Um intervalo cobrindo todos os dias do mês pode diferir do acumulado por esse motivo.
- As mensagens do painel identificam os registros sem data e os erros; não há preenchimento automático nem exclusão física.

Os filtros gerenciais atuam no **Painel inicial** e na seção **Relatórios gerenciais**, dentro de Relatórios. A tela de Produtividade existente permanece disponível com seus filtros de período e metas. A nova visão do painel oferece o ranking e os filtros combinados solicitados sem modificar essas metas.

Em Relatórios, a seção **Relatórios oficiais do mês — sem filtros gerenciais** permanece separada, com suas exportações originais. O Fechamento mensal e a confirmação do fechamento não recebem os filtros gerenciais. Os documentos gerenciais indicam seu período, filtros, revisão e finalidade; não substituem o fechamento oficial. Outubro/2026 continua sendo a competência inicial em andamento; setembro permanece consultável pelo seletor de referência.

## Consistência e atualização diária

As quantidades normais são agregadas diretamente das projeções existentes. Os feriados usam a mesma consulta de execuções já elegíveis/cobradas, incluindo o congelamento de meses fechados e a correção de Bocaina. Primeiro selecionam-se os vencedores globais do controle de duplicidades, **depois** são aplicados os filtros gerenciais. Filtrar um funcionário não elege outra execução nem realoca o adicional para outro registro.

Cada registro pertence a uma combinação de funcionário/cidade/grupo. Partições disjuntas dessas dimensões somam os totais do período. Seleções múltiplas usam pertinência, sem multiplicar linhas por repetição de opções. Não se deve somar relatórios com seleções sobrepostas como se fossem partições disjuntas: isso é uma sobreposição de relatórios, não uma nova cobrança.

O cache usa caminho dos dados, revisão, mês, preços, período, filtros e paginação. Importações, exclusões/restaurações e demais alterações já controladas pelo sistema invalidam a revisão. A visão gerencial verifica mudanças a cada 30 segundos enquanto está aberta e solicita nova execução do aplicativo quando a revisão muda. Na importação pela própria interface, o aplicativo já atualiza a navegação. Não é necessário reimportar nada.

As consultas gerenciais abrem SQLite em **somente leitura**, usam os índices existentes e fazem `SUM`, agrupamentos e paginação em SQL. O painel não carrega os registros brutos ou os Excel na memória. Não há migração, novos índices na produção ou alteração de backups. As exportações gerenciais são entregues em memória para download, sem gravar na pasta de dados.

## Instalar no Windows preservando os dados

1. Feche o Streamlit e faça seu backup habitual com o aplicativo fechado.
2. Extraia a versão atualizada em uma pasta temporária. Copie os arquivos de código sobre a instalação existente, **mesclando as pastas**. Preserve `data`, `.venv`, originais, backups, relatórios e configurações locais. O ZIP não inclui dados de produção ou ambiente Python.
3. Para uma atualização mínima, substitua **`app.py` e `cached_queries.py`** e acrescente **`managerial.py` e `managerial_ui.py`**, todos na pasta principal. Acrescente **`validar_gerencial.py`** se quiser executar a conferência de referência abaixo. Os demais módulos financeiros permanecem iguais. Testes, documentação e benchmark acompanham a versão completa, mas não são necessários para abrir o aplicativo.
4. Reinicie com seu iniciador habitual, ou, no terminal da pasta do sistema:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Não é necessário reinstalar Python ou dependências. O reinício elimina o cache da sessão antiga. Em Painel inicial, escolha a referência e período, combine os filtros e use a paginação. Para exportar a mesma seleção, use “Gerar Excel e PDF gerenciais da seleção”. Em Relatórios, a seção gerencial tem seu próprio seletor de período, e a seção oficial continua mensal.

Para reverter, restaure somente os arquivos de código anteriores com o aplicativo fechado. Não substitua o banco por uma versão antiga para reverter esta atualização: ela não migra dados.

## Conferência com a auditoria real de setembro

Os valores auditados fornecidos foram incluídos **somente como referência de teste**, em `tests/references/setembro_2026.json`; não são importados pelos módulos do painel ou pelo cálculo. A regressão aplica essa referência a uma fixture propositalmente diferente e verifica que a diferença é exibida, sem forçar coincidência.

Os 20 Excel e a base real de setembro continuam no computador do usuário. Não foi realizada uma nova validação desses registros no Codex. Para confrontar a nova visão gerencial com o JSON do cálculo independente já concluído, sem reler Excel ou alterar dados:

```powershell
.\.venv\Scripts\python.exe validar_gerencial.py --data data --reference .\validacao-setembro-2026\calculo_independente.json --output .\conferencia-gerencial-setembro.json
```

O arquivo de saída deve ser novo e fora de `data`. O comando compara as seis quantidades e o total e confere que cada dimensão, incluindo “Não informado”, reconcilia com o total. Espera-se `matches_reference: true`, todas as diferenças zeradas e as três `partition_totals_match` verdadeiras. Um resultado diferente será registrado, sem ajustar valores automaticamente. A referência pode também ser o `resultado.json` da auditoria anterior, desde que contenha resultados efetivamente calculados para o mês correto.

## Testes e desempenho

A suíte cobre os seis critérios existentes, filtros combinados, partições por dimensão e por combinação, ausência de data/identificação, seleção sem movimento, feriado com impressão inválida, duplicidade de execução entre funcionários, congelamento de feriados, exclusão/restauração, invalidação do cache ao importar um novo grupo, exportações Excel/PDF e preservação do fechamento oficial.

Validação final: **86 testes aprovados em 47,196 s**, sem testes ignorados. No original real de outubro disponível neste ambiente, a conferência gerencial coincidiu nas seis categorias e em R$ 30.454,12 com o JSON independente anterior; as três partições também reconciliaram. Isso não substitui a conferência de setembro na instalação Windows.

Em uma fixture **sintética de 500.000 registros**, com 60 funcionários, 20 grupos, cinco cidades e 6.000 combinações:

| Operação medida neste ambiente | Tempo |
| --- | ---: |
| Indicadores, sem cache do aplicativo | 0,52 s |
| Opções dos três filtros | 0,56 s |
| Ranking de até 50 funcionários | 0,67 s |
| Página de até 100 combinações | 1,06 s |
| Indicadores com os três filtros combinados | 0,52 s |
| Consulta por dia | 0,16 s |
| Excel com todos os agregados | 3,87 s |
| PDF resumido | 0,15 s |
| Quatro consultas do painel já cacheadas | 0,001 s |

As seis quantidades e as somas das partições coincidiram com a receita da fixture, e o banco sintético permaneceu byte a byte igual após as consultas/exportações. Os tempos medem funções do servidor, não renderização no navegador ou o computador Windows. Não incluem importação de Excel. O primeiro carregamento faz várias dessas consultas; o tempo de uma consulta isolada não deve ser apresentado como o tempo total da tela. Evidências e logs em `measurements/painel-gerencial`.

Não foi implementado módulo de Vistorias.
