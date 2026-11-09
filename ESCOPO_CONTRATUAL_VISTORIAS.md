# Vistorias: escopo permanente e critério de cobrança

Esta versão consolida as etapas anteriores. Leituras e seus seis critérios não foram alterados. Não precisa instalar versões intermediárias, reimportar arquivos ou reinstalar Python. Nenhum fechamento real foi aprovado e nenhuma glosa foi aplicada nesta entrega.

## Conciliação do Excel original de setembro/2026

Fonte: `576513-setembro sanesi.xlsx`, aba **Número OS**, 4.431 registros. SHA-256 antes e depois: `5c71eb3f941ae38d49b4afc8f612ad9da6b09cf0bc239a2d046f0bd47b410a58`.

O programa independente leu todos os registros, inclusive os ocultos, sem abrir banco de produção nem usar a tabela dinâmica ou totais manuais para determinar quantidades. Os totais SQL foram calculados em banco temporário separado. As duas apurações coincidiram:

| Serviço | Quantidade | Preço | Total |
|---|---:|---:|---:|
| Aprovação de ligação | 1.231 | R$22,50 | R$27.697,50 |
| Predial | 2.679 | R$22,50 | R$60.277,50 |
| Cadastral | 284 | R$12,00 | R$3.408,00 |
| **Total** | **4.194** | | **R$91.383,00** |

Conferência das 4.431 ocorrências preservadas: **4.194 cobradas + 12 sem cobrança adicional pela OS já representada + 223 fora do contrato + 2 não faturáveis = 4.431**. Não há pendências comerciais nessa fonte com o catálogo inicial confirmado. Geolocalização ainda depende das quantidades documentadas e não está incluída nesses valores. Este resultado é uma **prévia conciliada**, não aprovação do fechamento.

Na versão anterior, os 24 registros das 12 OS repetidas estavam integralmente pendentes. Agora representam 12 cobranças: aumento de **R$270,00** sobre R$91.113,00. A diferença para a referência de 1.243 aprovações é **−12**, pois a referência contava as duas ocorrências de cada OS. Não são serviços perdidos na importação.

As 223 ocorrências não permanecem pendentes: **161 de Araçoiaba da Serra e 62 de Macatuba estão fora do contrato**, conforme confirmação comercial. O Excel possui essas linhas ocultas pelo filtro municipal; a cópia Planilha5 contém somente as outras 4.208 linhas. A diferença entre abas não é usada como regra de classificação.

O TSS `VERIFICAR SERVIÇO EXECUTADO` permanece Predial, R$22,50: 277 ocorrências. O arquivo comprova os registros; o enquadramento e os preços vêm das confirmações comerciais, não das cores do Excel.

### Ocorrência escolhida das 12 OS repetidas

Critério confirmado: **última execução elegível**, não a última linha da planilha. Competência pela data dessa execução. Empate de horário: menor ID original, que corresponde à ordem de importação e depois à linha. As duas ocorrências continuam disponíveis no relatório detalhado, com arquivo, aba, linha, importação, motivo e representante escolhido.

| OS | Linha da aba Número OS | Última execução | Município |
|---|---:|---|---|
| 2634783960 | 1267 | 10/09/2026 09:03 | Tatuí |
| 2635691266 | 1070 | 09/09/2026 12:19 | Tatuí |
| 2636042316 | 2089 | 17/09/2026 13:06 | São Roque |
| 2636076615 | 1954 | 17/09/2026 16:18 | Boituva |
| 2636324254 | 1952 | 16/09/2026 05:50 | Botucatu |
| 2636495371 | **1400** | 14/09/2026 06:48 | Botucatu |
| 2636679534 | 1864 | 16/09/2026 15:22 | Torrinha |
| 2636693270 | 2957 | 24/09/2026 14:20 | Iperó |
| 2637223799 | 3117 | 25/09/2026 11:38 | São Roque |
| 2637502899 | 2362 | 18/09/2026 12:07 | São Roque |
| 2637543366 | 3118 | 25/09/2026 13:15 | Boituva |
| 2637874613 | 3119 | 25/09/2026 10:27 | Ibiúna |

A OS 2636495371 demonstra por que a ordem de linhas não pode escolher a cobrança: linha 1400 tem 06:48 e linha 1401 tem 06:47.

## Escopo contratual permanente

Acesse **Configurações → Municípios do Contrato**. Vigência inicial **2026-09 e todos os meses futuros**, até uma mudança explícita versionada. Não é uma exceção pontual de setembro. Araçoiaba da Serra e Macatuba ficam identificados como **Fora do escopo do contrato**. Não participam de faturamento, quantidades/produtividade contratuais, meta de 99% ou Fechamento Geral. Os registros e originais permanecem armazenados.

Lista inicial de 31 municípios autorizados, comprovados na base filtrada confirmada:

Agudos, Alambari, Alumínio, Anhembi, Araçariguama, Arealva, Areiópolis, Bocaina, Bofete, Boituva, Boraceia, Botucatu, Capela do Alto, Cesário Lange, Conchas, Dourado, Ibiúna, Iperó, Laranjal Paulista, Pederneiras, Pereiras, Piedade, Porangaba, Quadra, Salto de Pirapora, São Manuel, São Roque, Sarapuí, Tatuí, Torre de Pedra e Torrinha.

Normalização apenas de acentos, espaços e maiúsculas; não há aproximação de nomes. Município ausente ou desconhecido fica **pendente de autorização**, sem cobrança nem produtividade contratual automática. As listas de autorizados/excluídos não podem se sobrepor.

Para uma mudança futura: edite a lista completa, informe competência e documento/justificativa, clique **Calcular impacto do escopo**, confira valores e ocorrências/prazos antes/depois, marque a confirmação e clique **Confirmar escopo**. São guardados versões e histórico, inclusive substituições de uma versão ainda aberta. A simulação não persiste mudanças. Confirmação revalida importações, revisão e impacto atomicamente. Meses aprovados bloqueiam alterações retroativas.

Geolocalização por município aplica o mesmo escopo; quantidades fora do contrato ficam preservadas, sem cobrança. Município desconhecido com quantidade positiva bloqueia aprovação. No modo Total mensal, informe somente um total comprovadamente restrito ao contrato: um total sem discriminação não permite descobrir a participação de municípios excluídos. Não há dedução presumida de quantidades. Consulte as advertências e concilie a fonte documental antes de aprovar.

## Critério configurável por categoria

Em **Vistorias → Serviços e Tabela de Preços**, escolha a categoria e o critério:

- **Uma vez por OS**: inicial somente para Aprovação. Chave: contrato + categoria + OS, também entre competências abertas. Escolhe a última execução elegível. Se outra competência aberta passar a representar essa OS, o impacto no mês anterior aparece na prévia. Municípios divergentes entre candidatos ficam pendentes. Uma cobrança já aprovada não se desloca nem é cobrada novamente: a nova ocorrência fica para conferência.
- **Por execução**: após configuração explícita. Ocorrências com mesma OS, município e horário sem identidade unívoca ficam pendentes, evitando cobrança dupla automática. Uma decisão individual documentada continua disponível.
- **OS repetidas em conferência manual**: inicial para Predial, Cadastral e serviços novos. Não aplica automaticamente a regra de Aprovação às demais categorias.

Informe vigência e justificativa, calcule o impacto e confirme explicitamente. Não se sobrescreve um fechamento aprovado. Desconhecidos permanecem pendentes; serviços explicitamente não faturáveis não entram na receita. Alteração de critério não elimina execuções operacionais. Ambos os status devem ser Fechada; atrasos, aprovação ou recusa no campo resultado não criam uma nova exclusão comercial.

Se uma instalação antiga já persistiu `VERIFICAR SERVIÇO EXECUTADO` como Cadastral, o catálogo existente não é reescrito silenciosamente: selecione o TSS, Predial/200014106, preço específico vazio para seguir R$22,50, vigência confirmada e justificativa; confira o impacto e confirme. Setembro aprovado permanece bloqueado. Consulte também o editor e histórico em CATALOGO_VISTORIAS.md.

## Prazo e glosa

Prazo conta **ocorrências operacionais**, não OS cobradas. No original enviado, após o escopo confirmado: **4.208 apuráveis, 3.936 dentro e 272 fora: 93,5361% dentro do prazo**. Os 223 fora do contrato não participam do denominador. As 12 execuções sem cobrança adicional e os dois serviços não faturáveis continuam operacionais quando válidos.

Meta: 99%. Atraso não elimina faturamento. A glosa de 1% não é automática: depende de **Fechamento Geral validado** e confirmação explícita em **Aplicar multa**. Nenhuma glosa real foi calculada/aplicada nesta entrega.

## Backup, migração e recuperação

A única alteração estrutural é no banco **financeiro de Vistorias**, de versão 1 para 2: acrescenta município normalizado, timestamp e competência à projeção comercial, índices e um registro de cobranças congeladas para evitar nova cobrança de OS aprovadas. O banco operacional, o banco de Leituras e os Excel não são migrados nem alterados pelos testes.

Riscos: falta de espaço para backup/projeção, interrupção ou inconsistência prévia entre fonte e fotografia aprovada. Antes de qualquer alteração estrutural, o programa cria um backup SQLite consistente em `data/vistorias/backups/financeiro-antes-financeiro-<id>.sqlite3` e executa `integrity_check`. A migração é transacional, processa a origem em lotes de 2.000, não altera aprovações antigas e confere sua receita antes de reconstruir o registro de cobranças. Se não coincidir ou a origem estiver ausente/incompleta, cancela com rollback. Uma base com versão desconhecida é recusada.

Fotografias antigas sem escopo explícito conservam o comportamento histórico, incluindo municípios anteriormente considerados; **não corrigimos retroativamente um fechamento aprovado**. Para meses abertos e futuros aplica-se a nova política permanente. Operações e novos fechamentos guardam também a fotografia de prazos.

Antes de instalar, **pare o aplicativo com Ctrl+C e copie toda `data` para outra pasta**, mantendo backups existentes. Guarde também uma cópia do código da versão instalada. Essa cópia completa é o caminho mais simples de recuperação: com o aplicativo parado, volte ao código antigo e à cópia completa de `data` anterior à atualização. Preserve a pasta atual separadamente; não apague histórico. Não misture um banco financeiro antigo com importações posteriores. Restaurar apenas o backup automático financeiro requer que o banco operacional e suas importações ainda sejam os mesmos do momento do backup. Nunca copie/restaure bancos com Streamlit aberto.

## Atualizar Windows sem reinstalar Python

1. Pare o Streamlit; faça o backup completo acima.
2. Extraia o ZIP consolidado **em uma pasta temporária**, fora da instalação.
3. Copie os arquivos de código/documentação e `reference_data` para a pasta atual, substituindo as versões correspondentes. O pacote não contém `data`, `.venv`, `.streamlit`, bancos de produção ou Excel originais. **Preserve essas pastas e todos os backups.** Não apague arquivos da instalação.
4. Alternativa para instalação via Git, sem alterações locais de código: `git fetch origin` e `git switch codex/sistema-fechamento-pr`, depois `git pull --ff-only`. Se houver conflito, preserve suas alterações e não utilize reset/clean.
5. Não é necessário reinstalar Python ou dependências nesta atualização. Na pasta do aplicativo:

```bat
.venv\Scripts\python.exe -m streamlit run app.py
```

6. Na primeira abertura de Vistorias/Configurações, aguarde o backup e a preparação da versão financeira. Se a tela indicar projeção pendente, use **Preparar índices comerciais com backup**, sem reimportar Excel. Confira o escopo, os critérios e a conciliação. **Não aprova automaticamente setembro.**
7. Instalações novas, sem `.venv`, devem seguir a instalação inicial do README; não é o caso de uma atualização.

Arquivos alterados nesta etapa: `app.py`, `navigation.py`, `inspection_billing.py`, `inspections.py`, `inspections_ui.py`, `inspection_module_ui.py`, `validar_vistorias.py`, testes e documentação. Novos: `inspection_contract.py`, `inspection_settings_ui.py`, `benchmark_contract_scope.py`, `tests/test_inspection_contract.py`. O ZIP contém também os demais arquivos necessários da versão consolidada.

## Recalcular independentemente no Windows

A ferramenta não abre banco de produção; usa SQLite temporário e leitura sequencial do Excel. Não sobrescreve resultados existentes. Exporte o catálogo em Relatórios de Vistorias se sua instalação tiver regras/preços/conferências personalizados; inclui os contextos de outros meses e a ordem de importação para desempates. Para comparar OS entre meses, forneça os originais dos meses relacionados: a ferramenta só pode comprovar os arquivos fornecidos.

```bat
.venv\Scripts\python.exe validar_vistorias.py "C:\Originais\576513-setembro sanesi.xlsx" --mes 2026-09 --saida "C:\Conferencias\setembro-escopo-novo"
```

Com configuração exportada, acrescente `--catalogo "C:\Conferencias\catalogo-vistorias-2026-09.json"`. Sem catálogo usa o inicial confirmado; não presume configurações personalizadas. Para empate de horário sem catálogo, a ordem dos arquivos fornecidos e depois a linha define o desempate. Relatório Excel inclui motivo e origem da ocorrência representante para todos os registros. O JSON limita a amostra de representantes de OS repetidas a 1.000 e informa sua contagem completa, evitando uma lista ilimitada em RAM. Referências opcionais só são comparadas após a apuração.

## Verificação e desempenho

Executar em ambiente de testes, não na pasta de dados de produção:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`benchmark_contract_scope.py` compara a revisão anterior `568bc75` em bancos temporários separados, com 500 mil Leituras e 100 mil Vistorias sintéticas. Não mede navegador/rede nem importação Excel desse volume. O script de benchmark usa `resource` no Linux; não é necessário executá-lo para instalar no Windows. Tempos e resultados desta entrega são apresentados no relatório de validação; medições anteriores intermediárias ficam identificadas separadamente. Não há promessa de tempo universal para outro computador.
