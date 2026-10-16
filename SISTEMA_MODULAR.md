> **Documentação da etapa anterior.** Para as regras comerciais e a atualização consolidada atual, consulte [ESCOPO_CONTRATUAL_VISTORIAS.md](ESCOPO_CONTRATUAL_VISTORIAS.md). As quantidades e pendências desta etapa são históricas.

# Gestão modular do contrato Sabesp

## O que muda e o que permanece preservado

O menu tem seletor de módulos e páginas próprias. A identidade visual existente permanece. Leituras e Vistorias têm código e armazenamento separados. O Painel Geral e o Fechamento Geral só consultam o banco de Leituras em modo **somente leitura**; as seis regras auditadas, preços, feriados, Bocaina, filtros, exclusão/restauração e originais de Leituras não foram alterados.

A competência inicial continua outubro/2026 em andamento. O módulo inicial continua Leituras para preservar a rotina atual; Painel Geral aparece como primeira opção no seletor. Os nomes apresentados são Painel de Leituras, Importação de Leituras, Fechamento de Leituras, Produtividade e Relatórios de Leituras. Configurações mantém seus controles anteriores. No módulo Vistorias há sete páginas: Painel, Importação, Prazos e Meta Contratual, Serviços e Tabela de Preços, Geolocalização, Faturamento e Relatórios.

`readings_ui.py` contém a interface anterior de Leituras, movida com o mesmo corpo de instruções (comparação de AST realizada durante a extração). `app.py` faz a seleção e carrega apenas o ramo acessado. O painel de Vistorias não chama consultas nem importadores de Leituras. O Fechamento Geral é a integração explícita dos módulos, não uma mudança das regras de cálculo individuais.

## Riscos, backup e recuperação antes da atualização

**Riscos:** atualizar o aplicativo enquanto ele grava pode comprometer uma cópia manual do banco; selecionar uma aba copiada pode duplicar serviços; classificação/prévia não é fechamento aprovado; o primeiro preparo dos índices comerciais exige espaço em disco para projeção e backups. As aprovações são fotografias imutáveis nesta versão, portanto só aprove depois de conferir toda a conciliação. Não há reabertura financeira de Vistorias/Contrato nesta etapa; correções de fechamento aprovado exigirão um fluxo de nova versão auditável, não edição direta do SQLite.

**Procedimento seguro:**

1. Pare o Streamlit e feche todas as janelas do aplicativo.
2. Copie toda a pasta `data` para uma pasta de backup com data/hora, fora da instalação. Preserve também os backups anteriores e `.venv`.
3. Atualize somente os arquivos de código/documentação indicados abaixo.
4. Inicie o aplicativo. Se já havia vistorias importadas, utilize **Preparar índices comerciais com backup** ou **Atualizar projeção comercial dos registros existentes**. Isso não reimporta o Excel.
5. O primeiro preparo cria backups SQLite consistentes e verifica `PRAGMA integrity_check` antes da projeção. Os arquivos ficam em `data/vistorias/backups`. Nenhuma alteração estrutural é feita em `contrato.sqlite3` ou `vistorias.sqlite3`.
6. Para recuperar, pare o aplicativo, copie a pasta atual para outro local e restaure a cópia completa de `data`, com o código da versão correspondente. Não sobrescreva um SQLite enquanto estiver aberto. Os backups individuais são cópias verificadas dos bancos; a cópia completa da pasta também preserva Excel originais e a consistência entre módulos.

O banco operacional v1 de Vistorias é preservado; o financeiro utiliza um banco novo, sem migração do antigo. Versões desconhecidas do banco operacional/financeiro são recusadas. Nenhum banco de produção foi usado nos testes ou modificado na entrega. Os backups automáticos descritos ocorrerão na instalação local quando o usuário executar o primeiro preparo.

## Armazenamento

- `data/contrato.sqlite3` e `data/originais`: Leituras, sem mudanças nesta etapa.
- `data/vistorias/vistorias.sqlite3`: registros operacionais, originais, prazos e simulações históricas anteriores.
- `data/vistorias/originais`: arquivos XLSX integrais por SHA-256.
- `data/vistorias/financeiro.sqlite3`: catálogo, preços por vigência, projeção comercial, decisões, quantidades manuais de geolocalização, aprovações e histórico.
- `data/contrato_geral/consolidacao.sqlite3`: fotografias do fechamento total, glosas efetivamente aplicadas e histórico.

Os bancos novos só são criados ao acessar os respectivos módulos. A projeção comercial lê os registros existentes em lotes de 2.000 e acrescenta somente IDs novos. Não altera valores brutos. Quando a importação operacional termina mas a projeção falha, os registros operacionais continuam preservados; a interface orienta atualizar a projeção, e não reimportar. Enquanto ela estiver atrasada, a aprovação financeira fica bloqueada.

## Faturamento automático de Vistorias

Fonte inicial confirmada: **aba Número OS de 576513-setembro sanesi.xlsx**. A dinâmica OM e a cópia Planilha5 não são fontes de novos serviços. Somente OS Fechada e Operação Fechada entram como concluídas. A competência financeira usa Data Fim Execução. Atraso de execução não exclui cobrança quando os demais critérios comerciais estiverem satisfeitos.

Os códigos confirmados são 200014105 (aprovação, R$22,50), 200014106 (predial, R$22,50), 200014104 (cadastral, R$12,00). O mapeamento TSS fornecido pelo usuário está em `inspection_catalog.py`, inclusive a confirmação explícita de **EXAME PREDIAL ALTA DE CONSUMO COMP MD** como Predial. O catálogo inicial tem vigência a partir de setembro/2026; não presume tarifas ou classificações de períodos anteriores.

Normalização é limitada a caixa, acentos e espaços. Não há associação por similaridade, cores ou aproximação de descrições. Os originais ficam intactos. Os dois TSS confirmados em vermelho (`VERIFICAR USO DE FONTE ALTERNATIVA` e `VISTORIA DE PREPARAÇÃO DE ORÇAMENTO`) são excluídos da cobrança, sem apagar os registros operacionais.

As 12 OS repetidas têm 24 ocorrências que permanecem pendentes, sem cobrar automaticamente sequer a primeira. Os 223 casos de ligação inativa também permanecem separados e pendentes. A conferência individual permite cobrar ou excluir **somente aquele registro e competência**, com código confirmado, documento e confirmação explícita. Decisões não alteram o Excel nem o histórico de execução. Serviço não mapeado, regras específicas empatadas, preço ausente/inativo ou OS ausente ficam pendentes. A administração pode criar regras específicas de causa/formulário; regras mais específicas prevalecem, empate permanece pendente.

Duplicatas integrais entre importações cancelam toda a nova importação operacional, conforme a proteção anterior. Um mesmo arquivo não pode entrar novamente como outra aba. Não há exclusão automática de ocorrências diferentes da mesma OS.

Registros fechados sem data de execução não recebem competência presumida: aparecem como pendência global, bloqueando aprovação até conferência da fonte. Registros não concluídos permanecem operacionais e não são cobrados.

## Resultado efetivamente conferido no Excel enviado

A apuração SQL foi comparada com um segundo algoritmo que leu diretamente o Excel original, sem consultar banco de produção nem tabela dinâmica. Ambos apresentaram:

| Categoria | Quantidade faturável na prévia | Referência informada | Diferença | Valor da prévia |
|---|---:|---:|---:|---:|
| Aprovação de ligação | 1.219 | 1.243 | −24 | R$27.427,50 |
| Predial | 2.402 | 2.679 | −277 | R$54.045,00 |
| Cadastral | 561 | 284 | +277 | R$6.732,00 |
| Total de Vistorias, ainda provisório | 4.182 | — | — | **R$88.204,50** |

Além disso: 24 ocorrências de OS repetida e 223 ligações inativas pendentes; duas ocorrências excluídas pelo mapeamento confirmado. A soma é 4.431 registros, sem descarte. As 24 ocorrências repetidas são de Aprovação de ligação e explicam a retenção de 24 nessa categoria.

O TSS `VERIFICAR SERVIÇO EXECUTADO` tem **277 ocorrências** e foi enquadrado em Cadastral, conforme a lista confirmada pelo usuário. Esse número coincide com as diferenças opostas de Predial/Cadastral. **É hipótese, não comprovação**, que a referência anterior o tenha agrupado em Predial: a dinâmica disponível agrupa por TSS, não documenta por si só a associação às três categorias financeiras. Não movemos essas ocorrências para forçar coincidência. O relatório por TSS mostra integralmente a composição e os motivos para discussão comercial.

Há zero divergência entre o algoritmo independente e a prévia SQL para os três serviços, respeitando o mesmo mapeamento e as retenções comerciais. O valor é **prévia**, não aprovação automática. Não foi lançado o total de Geolocalização de setembro, nem calculado um Fechamento Geral real. O banco real de Leituras de setembro não está disponível aqui; R$596.906,23 e 19.951 feriados permanecem referências externas auditadas, não valores inseridos no aplicativo.

O SHA-256 do Excel permaneceu `5c71eb3f941ae38d49b4afc8f612ad9da6b09cf0bc239a2d046f0bd47b410a58`.

## Serviços, preços e vigências

A página administrativa permite consultar/adicionar código e serviço confirmados, editar preço, ativar/desativar e mapear/excluir TSS. Cada mudança registra justificativa, data/hora UTC, estado anterior e novo. Consultas mostram os últimos 50 eventos; todos continuam no banco. Catálogo e detalhes têm paginação de 50 linhas.

Vigências são AAAA-MM. Alterações que alcançariam qualquer competência já aprovada são recusadas. Aprovação preserva valores, serviços, quantidades, preços, revisão e geolocalização em fotografia mensal. Mudanças futuras não recalculam meses aprovados. A descrição de um código existente não é renomeada: use outro código contratual confirmado para outro serviço.

## Geolocalização

Preço inicial R$12,00. `geo` é identificador **interno**, não código tarifário inventado. O código contratual desse serviço ainda não foi fornecido.

Informe o modo principal: **Total mensal** ou **Por município**. O outro conjunto de dados, quando preenchido, é apenas referência. A cobrança usa exclusivamente o modo principal; não soma total e cidades. Divergências impedem aprovação. Uma única ficha por competência admite edições auditáveis enquanto não aprovada. Quantidades são inteiras e não negativas; município duplicado por caixa/acentos/espaços é recusado. Informe zero explicitamente se houver declaração documentada de ausência do serviço. Ausência de lançamento não é confirmação de zero.

A referência de setembro de 1.574 unidades/R$18.888,00 não foi cadastrada automaticamente.

## Conciliação, aprovação e Fechamento Geral

1. Importe ou prepare a projeção das vistorias existentes.
2. Confira catálogo e pendências individuais.
3. Registre Geolocalização a partir do documento Sabesp.
4. No Faturamento de Vistorias, informe referências opcionais da dinâmica e gere o relatório. Referências apenas calculam diferenças após a apuração; nunca definem as quantidades.
5. Confira diferenças, motivos e, se necessário, registros individuais. Gere o relatório novamente se os dados forem alterados.
6. Com pendências resolvidas e Geolocalização conferida, confirme explicitamente a aprovação. O servidor revalida a impressão digital do resultado e recusa confirmação desatualizada.
7. Feche Leituras pelo fluxo anterior, sem alterar seus critérios.
8. Abra Fechamento Geral. Só fica habilitada a validação definitiva quando Leituras estiverem fechadas e Vistorias/Geolocalização aprovadas.

**Leituras + Vistorias + Geolocalização = bruto mensal.** Antes da validação, a interface sinaliza claramente PRÉVIA e os componentes não aprovados. Depois, mostra fotografia mensal preservada, glosa aplicada e líquido. Os relatórios financeiros permanecem mensais; o módulo de prazos preserva mês, dia e intervalo, e os filtros anteriores de Leituras não modificam seu fechamento oficial.

## Glosa contratual

O prazo permanece: OS e operação Fechada, execução até o prazo final (com horário) está dentro, execução posterior está fora; meta de 99%. Resultado comercial e controle de prazo são independentes.

O botão **Aplicar multa** agora está no Fechamento Geral validado. A base vem do **total aprovado do contrato**, não de valor manual, somente Vistorias, ou um subtotal. Abaixo de 99%, e sem datas pendentes, o botão abre confirmação explícita. Só ao confirmar registra 1%, com arredondamento ao centavo metade para cima, fotografia da base/índice, motivo e data/hora. Uma chave única por competência e transação `BEGIN IMMEDIATE` impedem aplicação duplicada, inclusive entre sessões. Meta atingida, índice sem dados ou base não validada bloqueiam aplicação.

O fechamento bruto não é reescrito; a glosa é lançamento separado e o líquido é bruto menos a glosa. Não há cobrança bancária, publicação ou transmissão externa. As simulações históricas do módulo anterior continuam no banco operacional e visíveis em Prazos, identificadas como simulações; não são somadas como glosas efetivas do contrato.

## Conferência independente no Windows

O relatório normal do aplicativo é calculado das projeções originadas nos registros, sem dependência da dinâmica. Para uma segunda apuração diretamente dos Excel, use `validar_vistorias.py`:

```bat
.venv\Scripts\python.exe validar_vistorias.py "C:\Planilhas\576513-setembro sanesi.xlsx" --mes 2026-09 --saida "C:\Conferencias\vistorias-setembro-2026"
```

Sem `--catalogo`, utiliza exclusivamente o mapeamento/preços iniciais confirmados. Se houver alterações administrativas ou decisões individuais, em Faturamento/Relatórios clique **Preparar catálogo para validação independente**, baixe o JSON e acrescente:

```bat
--catalogo "C:\Conferencias\catalogo-vistorias-2026-09.json"
```

Opcionalmente `--referencias arquivo.json` recebe objeto com código e quantidade, apenas para a comparação após o cálculo. É possível passar vários Excel, cada original uma única vez. O script lê apenas Número OS, usa SQLite temporário para detectar OS repetidas e classifica com algoritmo próprio; não importa as funções de faturamento nem abre produção. Não releia Planilha5 como outra importação. Informa progresso e grava `calculo_vistorias.json` e `conferencia_vistorias.xlsx`. Uma pasta com esses resultados existentes é recusada para não sobrescrever a conferência anterior. O arquivo original é verificado por hash antes/depois. O JSON do catálogo é configuração, não contém quantidades de fechamento a alcançar.

## Atualizar o Windows sem reinstalar Python

Com backup completo e aplicativo parado:

```bat
cd C:\caminho\TESTE
git fetch origin
git checkout codex/sistema-fechamento-pr
git pull --ff-only origin codex/sistema-fechamento-pr
.venv\Scripts\python.exe -m streamlit run app.py
```

Se não usa Git, extraia o ZIP da atualização **na pasta atual do aplicativo**, substituindo somente os arquivos de código listados no `MANIFESTO.txt`. Não instale em uma pasta vazia: é uma atualização que reutiliza as dependências e demais arquivos existentes. Não substitua/apague `data`, `.venv` ou backups. Não há dependências novas nem reinstalação de Python. Se já importou a planilha no módulo de prazos, prepare apenas a projeção comercial; não reimporte.

## Arquivos desta etapa

Novos: `readings_ui.py`, `navigation.py`, `inspection_catalog.py`, `inspection_billing.py`, `inspection_module_ui.py`, `contract_finance.py`, `contract_ui.py`, `validar_vistorias.py`, `benchmark_modular.py`, `tests/test_modular_finance.py`, este documento e evidências em `measurements/modular-contract`.

Atualizados: `app.py` (roteamento), `inspections.py` (conexão rápida sem DDL repetitivo e proteção de competência aprovada), `inspections_ui.py` (separação de importação/simulação legada do prazo), `benchmark_inspections.py` e dois testes de navegação para a nova organização, além do README. Os arquivos das regras, consultas, preços e feriados de Leituras não foram alterados.

## Limitações de desempenho

A navegação consulta agregados e páginas limitadas, não carrega a base inteira. Cache financeiro é invalidado por importação/projeção, catálogo, conferência, geolocalização e aprovações. Excel é lido na importação ou na conferência independente explícita; a descoberta de abas do upload tem cache limitado. Exportações usam cursor/escrita sequencial e dividem no limite de linhas do Excel, mas o arquivo final ainda ocupa memória para download do Streamlit. Exportar milhões de registros pode exigir RAM e tempo significativos; não é iniciado ao abrir a página.

A evidência de desempenho mede 500.000 Leituras e 100.000 Vistorias sintéticas, em bases temporárias. Ela compara a versão anterior `608c111` com esta implementação, no servidor via AppTest, não rede/navegador nem uma importação Excel de 500 mil linhas. Consulte o relatório de medições e os logs para tempos efetivamente medidos. A primeira consulta mensal de Leituras ainda demora cerca de cinco segundos; as navegações com cache permanecem rápidas. Não há garantia universal de dois segundos em qualquer computador nem ensaio de vários anos de vistorias nesta entrega.


## Medições desta entrega

Mesmo ambiente e mesma base sintética: 500.000 Leituras e 100.000 Vistorias. Comparação da versão `608c111` com a versão modular. Consultas/execução da interface no servidor, não navegador ou rede. Três amostras cacheadas para Leituras; demais tempos são amostras individuais.

| Operação | Antes | Depois |
|---|---:|---:|
| Painel de Leituras · primeira consulta do mês | 5.204 s | 5.052 s |
| Painel de Leituras · com cache (intervalo das três amostras) | 0.064–0.068 s | 0.016–0.020 s |
| Consulta agregada de prazos | 0.044 s | 0.035 s |
| Navegação para Prazos | 0.091 s | 0.046 s |
| Entrada no módulo Vistorias/Painel financeiro | Não existia | 0.571 s |
| Consulta financeira de Vistorias (100 mil registros) | Não existia | 0.543 s |
| Painel de Vistorias com cache | Não existia | 0.041 s |
| Painel Geral inicial | Não existia | 1.029 s |
| Painel Geral com cache | Não existia | 0.008 s |

Preparação incremental inicial dos 100 mil registros, com backups: **1.479 s**. Os seis totais de Leituras permaneceram idênticos; o hash do banco sintético de Leituras ficou inalterado. Não houve regressão importante nas operações comparáveis medidas. A primeira consulta mensal de Leituras continua acima de dois segundos; esta entrega não altera suas consultas já auditadas.

Evidências: `measurements/modular-contract/results.json`, `before.json`, `after.json`, logs da suíte e `real-inspection-validation.json`. Scripts reproduzíveis: `benchmark_modular.py` (bases temporárias) e `validar_vistorias.py` (Excel original, relatório em outra pasta).


**Testes finais:** 105 testes passaram em 42,271 s; os dez testes específicos passaram em 0,726 s. Os testes de interface existentes foram adaptados apenas na navegação de Configurações/Vistorias. A extração da interface de Leituras inicialmente revelou uma dependência de `reference` que passou a ser parâmetro explícito; a suíte completa foi reexecutada após a correção. O corpo de instruções de Leituras permanece estruturalmente idêntico ao da versão anterior. As simulações históricas, a confirmação e a glosa definitiva são fluxos distintos; glosa definitiva duplicada é recusada pelo servidor.
