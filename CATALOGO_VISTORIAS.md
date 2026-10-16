> **Documentação da etapa anterior.** Para as regras comerciais e a atualização consolidada atual, consulte [ESCOPO_CONTRATUAL_VISTORIAS.md](ESCOPO_CONTRATUAL_VISTORIAS.md). As quantidades e pendências desta etapa são históricas.

# Correção de classificação e edição segura do catálogo de Vistorias

Esta entrega retifica o mapeamento comercial de **VERIFICAR SERVIÇO EXECUTADO** para **Vistoria Predial, código 200014106, R$22,50**, conforme a nova confirmação do usuário. Substitui, nesse ponto, o mapeamento e a prévia descritos na documentação anterior. Não modifica código, preços, regras, calendário ou fechamento de Leituras.

## Conciliação de setembro, antes de qualquer validação

O Excel original `576513-setembro sanesi.xlsx`, aba Número OS, contém 277 linhas com esse TSS, todas com OS e operação Fechada. O arquivo comprova descrição, status e registros; não contém preço nem código tarifário. O enquadramento comercial e o preço são sustentados pela confirmação explícita do usuário, não inferidos de cores ou das quantidades de referência.

A configuração anterior foi reproduzida somente em banco temporário. O segundo cálculo leu diretamente o Excel, com algoritmo independente, e coincidiu com o resultado SQL após a correção.

| Categoria | Antes | Depois | Valor depois | Referência informada | Diferença de quantidade |
|---|---:|---:|---:|---:|---:|
| Aprovação de ligação | 1.219 | 1.219 | R$27.427,50 | 1.243 | −24 |
| Predial | 2.402 | 2.679 | R$60.277,50 | 2.679 | 0 |
| Cadastral | 561 | 284 | R$3.408,00 | 284 | 0 |
| **Total provisório** | **4.182** | **4.182** | **R$91.113,00** | — | — |

O total anterior era R$88.204,50. A alteração de 277 linhas de R$12,00 para R$22,50 produz **+R$2.908,50**, calculados por registro. A quantidade total faturável não mudou. As referências só entraram na comparação após a apuração; não foram usadas para determinar quantidades.

**Setembro continua não aprovado.** Permanecem 247 ocorrências pendentes: 24 de OS repetidas e 223 de ligação inativa. Há também duas ocorrências não faturáveis pelo mapeamento já confirmado. A conferência fecha em 4.431 linhas, sem descarte: 4.182 faturáveis na prévia + 247 pendentes + 2 excluídas comercialmente. A Geolocalização não foi lançada e o Fechamento Geral real não foi validado.

### O que ocorreu com as 24 aprovações

São 24 linhas de **12 OS que aparecem duas vezes**, não registros perdidos na importação. Todas pertencem aos TSS de Aprovação de ligação. O sistema mantém as duas ocorrências de cada OS para conferência, conforme decisão comercial anterior, sem escolher automaticamente uma para cobrar.

A investigação dos campos originais identificou:

- **8 pares com causas/resultados diferentes:** seis passaram de recusado para aprovado; um mudou entre dois motivos de recusa; um passou de aprovado com pendência para aprovado.
- **2 pares com o mesmo resultado de recusa em datas diferentes.** Pode haver revisita, mas o arquivo não comprova seu direito de cobrança.
- **2 pares com diferença apenas na conclusão/Tempo Residual, de um minuto**, em 14/09 e 18/09. Pode ser correção operacional, não prova de duas visitas faturáveis.

A planilha de investigação lista as 12 OS, suas 24 linhas originais, datas, causas, formulários e campos que diferem. Não são 24 duplicatas exatas comprovadas. Não foi descartado nem liberado qualquer registro. Se todas as 24 ocorrências fossem futuramente comprovadas faturáveis, o valor adicional seria R$540,00; **isso é uma condição hipotética, não autorização nem ajuste aplicado**.

### As 223 ligações inativas

TSS `VISTORIA LIGAÇÃO INATIVA SEM DÉBITO`, todas com causa `DEMOLIDO SEM ABASTECIMENTO NORMAL`: 161 em ARACOIABA DA SERRA e 62 em MACATUBA. Não há categoria/preço comercial confirmado para elas. Continuam separadas, sem cobrança e preservadas no controle operacional de prazos. Não foi estimado preço para esse conjunto.

### Os 277 registros corrigidos

Há 274 com causa `VISTORIADO LOCAL EXECUÇÃO CONFIRMADA`, um com `IMÓVEL FECHADO, ORDEM ENCERRADA`, um com `TRATA-SE DE OUTRO SERVIÇO` e um com `RESPONSABILIDADE DE OUTRA CONCESSIONÁRIA`. Todos permanecem sujeitos aos critérios comerciais vigentes: TSS confirmado e ambos os status Fechada. Não criamos uma exclusão adicional pelos três resultados atípicos. Eles estão destacados no relatório para eventual decisão comercial explícita futura.

SHA-256 do Excel antes/depois: `5c71eb3f941ae38d49b4afc8f612ad9da6b09cf0bc239a2d046f0bd47b410a58`.

## Editor no aplicativo

Acesse **Vistorias → Serviços e Tabela de Preços**.

- Escolha uma descrição TSS existente ou **Nova descrição**.
- Defina categoria/código confirmado, situação **Faturável**, **Não faturável** ou **Pendente**, competência inicial e documento/justificativa.
- Descrição desconhecida permanece pendente por padrão. Não há classificação aproximada.
- O campo **Preço específico deste TSS** permite remunerar somente essa descrição por valor diferente da categoria. Exemplo: Predial permanece com tarifa-base R$22,50, mas esse TSS pode passar a R$12,00 em uma competência futura sem mudar os demais prediais.
- Campo de preço específico vazio significa seguir a tarifa da categoria a partir da vigência informada, encerrando um preço específico anterior. Preços podem ser zero explicitamente; não se presume quantidade ou valor inexistente.
- Preços específicos abrangem o TSS inteiro. Regras com causa/formulário específicos podem definir elegibilidade/categoria, mas não preço específico por causa. Regras mais específicas prevalecem; empates ficam pendentes.
- Decisões individuais de conferência já registradas continuam tendo prioridade sobre a classificação geral. Não são apagadas por uma mudança de catálogo; confira seu efeito no impacto por categoria.
- O bloco **Serviço/preço** altera o preço-base de uma categoria ou adiciona serviço com código contratual confirmado. A prévia demonstra o efeito sobre todas as descrições que utilizam essa tarifa.

As versões são guardadas por competência. O histórico, paginado em 50 eventos, registra estado anterior, alteração proposta, documento, data/hora UTC e impacto confirmado. A tabela do catálogo também é paginada; o carregamento do formulário não varre registros nem recalcula faturamento.

### Antes de salvar

1. Clique **Calcular impacto da classificação** ou **Calcular impacto do serviço/preço**.
2. Confira valores anteriores/posteriores, diferenças, quantidades por categoria e pendências em **todas as competências existentes abrangidas pela vigência**.
3. Nenhuma classificação/preço foi persistido nesta etapa: a simulação usa savepoint e rollback no banco financeiro, sem copiar toda a base ou alterar registros originais.
4. Marque a confirmação e clique **Confirmar alteração após impacto**.
5. O servidor revalida revisão, importações, impacto e vigência dentro de transação. Uma prévia desatualizada é recusada; gere outra. A confirmação não aprova o faturamento mensal.

Mudanças que alcançariam meses já aprovados são recusadas. Fotografias de fechamento anteriores, preços, regras e conferências permanecem intactos. Alterar apenas uma tarifa futura não recalcula meses aprovados. A prévia só é executada ao solicitar; não é refeita a cada mudança de campo.

## Atualização de uma instalação que já possui o catálogo anterior

Instalações novas recebem o mapeamento corrigido como configuração inicial. **Um catálogo já persistido não é reescrito silenciosamente na atualização.** Com setembro ainda aberto:

1. Abra Serviços e Tabela de Preços.
2. Em Descrição TSS para editar, selecione `VERIFICAR SERVICO EXECUTADO` (o seletor apresenta a chave normalizada, sem acentos).
3. Escolha **Vistoria predial — 200014106** e situação **Faturável**.
4. Deixe o preço específico vazio para seguir os R$22,50 da categoria, e informe vigência **2026-09** e a justificativa da correção confirmada.
5. Calcule e confira o impacto. Na base enviada, sem outras alterações de catálogo/conferências, o aumento é R$2.908,50. Se sua base tiver mudanças adicionais, use a prévia real apresentada, não force esse valor.
6. Confirme a alteração; gere novamente a conciliação de setembro. Não aprove o mês enquanto as pendências comerciais não estiverem resolvidas.

Se setembro já estiver aprovado, a alteração retroativa será bloqueada. Esta entrega não reabre nem reescreve fechamento aprovado.

## Banco, backup e Windows

Não há alteração estrutural de banco. Preços específicos versionados utilizam a tabela de metadados já existente; não são adicionadas colunas/tabelas nem migrado o banco operacional ou de Leituras. Os registros originais não são editados.

Com o aplicativo parado, copie **toda `data`** para backup externo e preserve backups anteriores. Atualize o código via Git na branch `codex/sistema-fechamento-pr`, ou extraia o pacote de código na instalação atual. O pacote não contém `data`, `.venv` nem Excel originais. Não apague essas pastas e não precisa reinstalar Python ou dependências. Inicie:

```bat
.venv\Scripts\python.exe -m streamlit run app.py
```

Depois de gravar preços específicos, não faça downgrade apenas do código: uma versão antiga não conhece essas tarifas. Para recuperar uma versão anterior, pare o aplicativo, preserve a pasta atual e restaure o backup completo com o código correspondente.

## Reproduzir a auditoria do Excel

O diagnóstico usa apenas o arquivo informado e bancos temporários. Não abre banco de produção, não importa vistorias no aplicativo e não aprova mês. A pasta de saída deve ser nova:

```bat
.venv\Scripts\python.exe auditar_catalogo_vistorias.py --excel "C:\Planilhas\576513-setembro sanesi.xlsx" --mes 2026-09 --saida "C:\Conferencias\catalogo-setembro-corrigido"
```

Gera conciliação, recálculo independente, JSON e Excel com os 277 registros e as 247 pendências identificadas por linha original. A análise detalhada de OS é dimensionada para esse arquivo de 4.431 registros; não é um benchmark de auditoria de milhões de linhas. O aplicativo utiliza SQL agregado e paginação.

Opcionalmente `--referencias arquivo.json` permite comparar quantidades informadas por código; elas são usadas somente depois de calcular. O `validar_vistorias.py` também foi atualizado para respeitar preços específicos e situação Pendente do catálogo exportado.

## Arquivos desta etapa

Código alterado: `inspection_catalog.py`, `inspection_billing.py`, `inspection_module_ui.py`, `validar_vistorias.py`. Código novo: `auditar_catalogo_vistorias.py`, `benchmark_catalog.py`. Testes novos: `tests/test_catalog_changes.py`. Guia e evidências: este documento, README e `measurements/catalog-correction`.

Nenhum arquivo de implementação do módulo de Leituras foi alterado. A nova conciliação não valida setembro nem libera as 247 pendências.


## Testes e desempenho medidos

**113 testes passaram em 42,087 s**, incluindo oito específicos em 0,738 s. Cobertura: correção em instalação nova e catálogo antigo, rollback da prévia, confirmação explícita, rejeição de prévia desatualizada, preços por TSS sem alterar outras descrições, situações não faturável/pendente, retorno ao preço-base, vigências por mês, bloqueio retroativo, preservação de snapshots, recálculo independente e interface em duas etapas. A regressão anterior de Leituras permaneceu aprovada.

Benchmark isolado de **100.000 vistorias sintéticas**, mesma base, Python e ambiente, comparando o commit anterior `57c8290` com esta implementação. São consultas SQL sem cache de aplicação, não tempo de navegador, rede ou importação Excel.

| Operação | Antes | Depois |
|---|---:|---:|
| Resumo financeiro — intervalo de três amostras | 0.460–0.462 s | 0.480–0.490 s |
| Resumo — mediana | 0.460 s | 0.482 s |
| Prévia exata de impacto em 100 mil registros | Não existia | 1.101 s |

Os valores/quantidades sintéticos permaneceram iguais no resumo comparável; a simulação deixou o banco financeiro byte a byte igual. O custo adicional da prévia ocorre somente ao clicar, e o formulário carrega apenas o catálogo e páginas do histórico. Consultas continuam agregadas e o cache é invalidado após confirmar alterações. A busca da vigência de preço específico usa janela SQL sobre o catálogo, sem procura correlacionada a cada registro. Não houve ensaio novo de milhões de registros; o benchmark anterior de 500 mil Leituras permanece como evidência anterior, não foi apresentado como nova execução.

Evidências em `measurements/catalog-correction`. No relatório real, registros/OS detalhados permanecem somente nos arquivos de conferência entregues, sem planilhas de clientes anexadas ao repositório.
