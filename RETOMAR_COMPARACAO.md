# Retomar a comparação sem reler os Excel — Windows

## Atualizar somente um arquivo

Feche a ferramenta e o Streamlit. No pacote de correção, substitua **somente** `validacao_independente\validacao_independente.py` pelo arquivo novo, na mesma subpasta criada pelo ZIP anterior. Os demais módulos continuam iguais. Se você executava o script diretamente na pasta principal, substitua somente esse `validacao_independente.py` e use o segundo comando abaixo.

Não substitua nem apague `validacao-setembro-2026`, `data`, `.venv`, originais ou backups. Não é necessário reinstalar Python ou pacotes. O cálculo original de R$ 596.906,23 informado pelo usuário não é editado nem se torna um valor-alvo do programa.

No terminal aberto na pasta principal do sistema, execute:

```powershell
.\.venv\Scripts\python.exe .\validacao_independente\validacao_independente.py --data .\data --somente-comparacao .\validacao-setembro-2026 --output .\comparacao-setembro-2026
```

Se o script estiver diretamente na pasta principal:

```powershell
.\.venv\Scripts\python.exe .\validacao_independente.py --data .\data --somente-comparacao .\validacao-setembro-2026 --output .\comparacao-setembro-2026
```

Informe o caminho real em `--data` se usa pasta personalizada. O mês vem dos arquivos salvos; não é necessário informar `--month`. A pasta de saída precisa ser nova, fora de `data` e fora da validação original. Para repetir, use `comparacao-setembro-2026-2`, por exemplo.

São necessários `entradas.json` e `calculo_independente.json`, criados antes da interrupção na pasta `validacao-setembro-2026`. Esse modo **não abre nenhum Excel**, nem precisa que os arquivos originais sejam lidos novamente. O programa confere o hash do manifesto e a consistência interna das seis quantidades/preços/total. Confere também a revisão, preços e identidade das importações no banco antes de comparar. Se a base mudou, a comparação é recusada; não se apaga nem se ajusta o cálculo salvo para contornar a recusa.

## Resultados e limites da retomada

Na pasta nova serão gerados:

- `comparacao.xlsx`: seis quantidades independentes salvas versus seis quantidades do banco, diferenças e valores em centavos.
- `comparacao.json`: os resultados, hashes de proveniência, escopo, limitações e tempos medidos por etapa.
- `RELATORIO_COMPARACAO.md`: relatório legível da comparação.

O arquivo `calculo_independente.json` original não é sobrescrito. O banco de produção é aberto em `mode=ro`; não existem migrações ou gravações nele. Só um banco temporário separado recebe os IDs de feriados. Os preços, os seis critérios, as exclusões/restaurações, os feriados congelados e a política municipal de Bocaina continuam iguais.

**O JSON antigo guarda agregados, não os resultados independentes por linha.** A versão anterior removia o banco temporário de detalhes ao interromper. Portanto, a retomada compara por serviço e total; não comprova igualdade registro a registro. Isso fica explícito em `detail_comparison_available: false` e `app_details_match_aggregates: null`. Uma diferença individual entre resultados independentes só pode ser recuperada com os detalhes de uma execução completa ou com novo recálculo dos originais. A ferramenta não inventa esses detalhes a partir dos totais nem finge retomá-los.

Confira todas as seis `delta_quantities`, além de `delta_cents`. Um total igual pode ocultar diferenças compensatórias entre serviços; mesmo seis quantidades iguais não substituem a conferência de cada registro. Se houver diferença, ela será exibida sem ajustar nenhum dos lados.

## Gargalo e correção

A linha `batch.append(tuple(row))` do traceback não identifica, sozinha, um gargalo no Python. A iteração estava buscando a próxima linha de uma consulta SQL que fazia `LEFT JOIN` entre cada registro e uma consulta complexa de feriados. No teste sintético, o plano dessa junção contém `SCAN m LEFT-JOIN`: o conjunto derivado não tem um índice adequado para essa procura. O problema foi reproduzido neste ambiente; não foi necessário alterar as regras para eliminá-lo.

A comparação agora:

1. Soma as cinco categorias por SQL agregado, sem calcular indicadores de interface ou procurar conflitos desnecessariamente.
2. Consulta os IDs de feriados uma única vez usando a mesma regra e o mesmo comportamento de congelamento anteriores.
3. Materializa os IDs em uma tabela temporária com chave primária, fora da base de produção.
4. Na execução completa, transfere os registros em lotes e faz a junção indexada apenas no banco temporário. Na retomada agregada, dispensa inteiramente essa transferência.

Há mensagens de etapa, progresso a cada 10.000 IDs/registros e sinalização a cada aproximadamente dois segundos de execução SQL prolongada. Na execução completa, a geração dos relatórios também informa o progresso a cada 10.000 linhas. O progresso não inventa uma porcentagem nem promete um prazo.

## Testes e medições

Foi criada uma base **sintética e isolada** com 379.523 registros, 20 grupos e 18.072 execuções em feriado. Os registros têm JSON com campos de leitura e preenchimento adicional, e o arquivo SQLite tem aproximadamente 532 MB. As quantidades são definidas pela receita sintética; o teste não é uma validação dos dados reais de setembro e não mede importação ou recálculo de Excel.

As medições e os planos completos estão em `measurements/comparacao-retomada/results.json`. A consulta antiga foi limitada explicitamente a dez segundos: se interrompida, seu tempo total não foi medido nem extrapolado. A nova comparação concluiu os 379.523 registros, e a retomada agregada gerou os relatórios sem ler Excel. As seis diferenças foram zero, conforme a receita da fixture. Esses tempos dependem do computador e não são promessa para o Windows.

| Execução final neste ambiente | Resultado medido |
| --- | --- |
| Comparação antiga | 4.822 registros em 10,00 s; interrompida pelo limite do benchmark |
| Comparação otimizada completa | 379.523 registros em 1,60 s, sem exportação detalhada de todos os originais |
| Retomada agregada do JSON | 0,37 s, incluindo Excel, JSON e Markdown da comparação |

A suíte completa terminou com **79 testes aprovados em 47,559 s**, sem testes ignorados. As medições não representam uma validação dos 379.523 registros reais de setembro, que não estão disponíveis no Codex.

A suíte inclui: reutilização do JSON legado com abertura de Excel proibida por teste; preservação byte a byte dos arquivos salvos e banco; recusa de manifesto divergente, cálculo inconsistente, revisão antiga e base diferente; detecção de diferenças financeiras reais sem alterar os valores salvos; regressões das seis regras, feriados, Bocaina, exclusões e restaurações. Os resultados de execução estão junto das medições.

Para desenvolvedores reproduzirem o teste em um checkout Git com histórico:

```powershell
.\.venv\Scripts\python.exe benchmark_independent_compare.py --output benchmark-comparacao --rows 379523 --baseline-timeout 10
```

O benchmark acessa apenas o banco sintético que cria em pasta temporária. Não forneça um caminho de produção a esse script; ele não tem parâmetro de base existente. O tempo anterior vem da função da versão `3a62b0e`, não de uma estimativa.
