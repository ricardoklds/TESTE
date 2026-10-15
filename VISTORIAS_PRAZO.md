# Vistorias — meta contratual de prazo

A tela **Vistorias**, no menu lateral, apura somente prazo operacional. As seis regras de faturamento, preços e banco `data/contrato.sqlite3` não são modificados por esse módulo. Nenhuma vistoria é faturada nesta atualização.

## Operação

1. Escolha o mês na lateral e abra Vistorias.
2. Expanda **Importar base de vistorias**, envie o Excel, escolha **uma única aba de registros originais** e confirme explicitamente seu escopo antes de importar. A tabela dinâmica é recusada por não conter os cabeçalhos obrigatórios. Não some Número OS e Planilha5.
3. Selecione mês completo, dia ou intervalo. O período usa **Data Fim Execução**, não Data de Competência.
4. Confira o indicador geral e a tabela de municípios. A meta é 99%; a barra mostra o resultado real, com referência textual de 99%. A tabela usa barras percentuais.
5. Gere o Excel apenas se necessário. O resumo e os municípios são sempre incluídos; o detalhamento de atrasos é opcional, com arquivo, aba, linha, OS, TSS e datas originais.

Base operacional: Status da OS e Status da Operação iguais a Fechada (ignorando espaços periféricos e caixa). Encerradas com resultado recusado, imóvel fechado ou glosa continuam na apuração de prazo, conforme solicitado. Fim de execução **menor ou igual** ao prazo final é dentro do prazo; superior é fora. Prazo inicial e Tempo Residual são conservados para conferência e não substituem essa comparação. Não são aplicadas regras de feriados/domingos da leitura ao prazo das vistorias.

OS repetidas com datas/resultados diferentes permanecem como ocorrências, com aviso e confirmação explícita na importação; isso não estabelece direito de cobrança. Duplicatas de dados integrais entre arquivos provocam cancelamento da transação inteira, sem inclusão parcial. Arquivos idênticos não são importados novamente, mesmo escolhendo outra aba. O original é arquivado byte a byte por SHA-256.

Datas insuficientes ficam como **Pendente de data**. Não são classificadas como pontuais ou atrasadas. O denominador mostrado é identificado como “vistorias com prazo apurável”, sem esconder a limitação. Pendências com execução no período e pendências sem data de execução são avisadas separadamente do indicador; sem data não se presume competência. Enquanto existirem tais pendências, a apuração é provisória e multa permanece bloqueada. Não há imputação de datas para satisfazer a meta. Município ausente permanece Não informado.

## Multa e fechamento total do contrato

Abrir a tela **não calcula multa**. O botão Aplicar multa é habilitado somente para período apurável com índice abaixo de 99% e sem pendências de data. Após clicar, informe o **valor total documentado do contrato** em reais (formato brasileiro, por exemplo `100000,00`) e documento/responsável, e marque a confirmação explícita. O total das leituras não é assumido como total contratual, pois o aplicativo ainda não possui faturamento completo de vistorias/outros itens.

Somente ao confirmar o sistema recalcula a elegibilidade, calcula 1% da base informada, arredondado ao centavo pelo método metade para cima, e registra índice, período, valor bruto, multa, líquido simulado e hashes das importações. Data/hora do histórico são UTC. O histórico exibe os 50 eventos mais recentes; todos continuam armazenados. Cada confirmação gera evento novo, não sobrescreve eventos anteriores.

**O registro é um cálculo auditável de glosa, não um lançamento financeiro automático.** O fechamento oficial, faturas, preços e históricos de leituras permanecem intactos. Não há inferência de qual valor corresponde ao fechamento geral; a confirmação documental é responsabilidade do usuário. O eventual desconto financeiro precisará de fluxo próprio autorizado.

## Armazenamento, backup e recuperação

O módulo cria **somente** `data/vistorias/vistorias.sqlite3` e `data/vistorias/originais/`. Não migra nem altera a estrutura do banco de leituras. Não existe migração de bancos antigos de vistorias nesta versão: uma versão desconhecida é recusada.

Antes de atualizar, pare o Streamlit e copie **toda a pasta data** para uma pasta de backup com data/hora, fora da pasta do aplicativo. Preserve `.venv` e backups existentes. Essa cópia abrange banco de leituras, originais, feriados e, nas próximas atualizações, o banco próprio de vistorias. Para recuperar, com o aplicativo parado, preserve primeiro a pasta atual em outro local e restaure a cópia completa. Não sobreponha arquivos SQLite enquanto o app estiver aberto. Nenhum backup de produção foi criado pelo Codex porque esta entrega não atualiza a estrutura desse banco nem acessa sua instalação Windows.

## Atualizar no Windows sem reinstalar Python

Com o aplicativo parado e backup feito:

```bat
cd C:\caminho\TESTE
git fetch origin
git checkout codex/sistema-fechamento-pr
git pull --ff-only origin codex/sistema-fechamento-pr
.venv\Scripts\python.exe -m streamlit run app.py
```

Se não utiliza Git: substitua `app.py`, adicione `inspections.py`, `inspections_ui.py` e este documento, a partir do ZIP da atualização. Não substitua nem apague `data`, `.venv`, Excel ou backups. Não há dependência nova. Não copie o Excel automaticamente para produção: a importação de vistorias depende da seleção e confirmação da aba na interface.

## Desempenho e validação efetivamente medida

- Lotes de 2.000 linhas, transação única por importação e índice de período/status/município.
- SQL agregado para resumo e municípios; nenhuma leitura do Excel na navegação.
- Cache do resumo por banco, versão de importações e período. Não há edição de registros nesta versão; cada nova importação altera a chave.
- Excel detalhado é gerado somente sob demanda, com cursor SQL e escrita sequencial, dividido no limite de linhas. O arquivo final ainda é materializado em memória para download Streamlit; exportações muito grandes podem consumir RAM. A interface carrega apenas a agregação municipal e os últimos 50 eventos.
- `measurements/inspection-deadlines/results.json` contém medições deste ambiente. Não são promessa de tempo no Windows.
- Excel enviado, aba Número OS, em base **temporária**: 4.431 ocorrências, 4.159 dentro, 272 fora, **93,8614308%** dentro, zero pendências de data, 33 municípios. Importação medida: **0,704 s**. Resultado condicionado à inclusão de toda essa aba e à contagem das ocorrências repetidas; nenhuma base de produção foi importada ou alterada e nenhuma multa foi calculada sobre ela.
- 500.000 registros **sintéticos**, inseridos por SQL em lotes: resumo geral e 100 municípios em **0,181 / 0,183 / 0,236 s**. Esse teste mede consulta, não importação Excel de 500 mil linhas.
- Exportação sintética de 5.000 atrasos + resumo: **0,317 s**. Dados sintéticos têm campos brutos reduzidos e alta compressão; não representam o tamanho de um Excel real.
- AppTest verificou abertura da nova tela, sem exceção, e card de meta presente. Testes cobrem limite inclusivo, atraso, datas inválidas, estados, duplicatas/rollback, períodos, municípios, exportação, meta exata de 99%, confirmação e arredondamento da multa. Regressão completa: **95 testes passaram em 46,814 s**, incluindo os cinco testes específicos; registro em `measurements/inspection-deadlines/regression-tests.txt`. A primeira execução ampliada identificou interferência de configuração entre testes; o teste de interface passou a isolar explicitamente a pasta temporária, e a suíte completa foi reexecutada com sucesso.

Não foi feito ensaio de milhões de vistorias nesta entrega nem alteração das fórmulas comerciais de leitura. Para conferir as 12 OS repetidas e as 223 inativas, use a análise estrutural entregue anteriormente e a confirmação de escopo da importação.
