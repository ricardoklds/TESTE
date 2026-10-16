# Serviços editáveis e prévia gerencial do Fechamento Geral

Esta atualização altera somente a administração de preços de Vistorias e a composição/exportação do Fechamento Geral. Menu expansível, Painel Geral, Leituras, feriados, importações, produtividade, prazos/meta de 99%, escopo municipal, cobrança única por OS, Geolocalização simplificada e controle de glosa permanecem preservados. Nenhum preço ou classificação existente é atualizado ao instalar ou abrir uma página. Não há migração nova ou alteração estrutural de banco.

## Tabela de serviços

Em **Configurações → Serviços e Preços de Vistorias**, a tabela permite editar preço, vigência proposta e situação. Código e descrição de serviços existentes são preservados. Os preços exibidos vêm do cadastro atual; não são redefinidos pelos preços iniciais. A vigência proposta começa no mês selecionado, conforme indicação acima da tabela; as vigências efetivamente cadastradas aparecem na seção expansível abaixo.

1. Edite as linhas necessárias.
2. Clique **Salvar alterações** para conferir o impacto consolidado nas competências abertas. A proposta ainda não foi persistida.
3. Confira os valores antes/depois e confirme. Se houver desativação, marque também **Confirmo a desativação dos serviços indicados**.

A gravação de várias linhas é atômica: uma linha inválida cancela o lote inteiro. Histórico registra estado anterior, novas condições, data/hora UTC e impacto. Nenhum serviço é excluído fisicamente. Uma prévia desatualizada ou que alcance competência aprovada é recusada. A confirmação de preços não aprova fechamento.

**Adicionar serviço** abre um cadastro compacto de código, descrição, valor e vigência. Códigos já cadastrados são recusados. Um novo serviço não classifica automaticamente TSS existentes nem cria cobranças; é necessário enquadramento comercial explícito.

## Classificação dos serviços TSS

A seção separada permite selecionar a descrição, categoria, situação, preço específico opcional e vigência. A situação Pendente continua disponível para preservar serviços desconhecidos sem cobrança automática. Critérios opcionais já existentes de causa/formulário permanecem disponíveis. Regras comerciais por OS continuam na página própria, sem alteração.

Preço específico vazio segue a categoria. Por exemplo, uma alteração futura de apenas `VERIFICAR SERVIÇO EXECUTADO` para R$12,00 pode conservar sua categoria Predial sem mudar os demais prediais. Isso é uma possibilidade do editor, **não uma alteração aplicada nesta entrega**. A diferença financeira é exibida antes da confirmação; preços/classificações históricos e fechamentos aprovados são preservados.

## Composição do Faturamento

Somente no **Fechamento Geral**, a seção expansível mostra os seis serviços de Leituras, os três serviços confirmados de Vistorias e Geolocalização, com código, descrição, quantidade faturável, preço e total. Se o cadastro for ampliado explicitamente, serviços adicionais existentes também são mostrados, evitando ocultar receita cadastrada.

Os componentes continuam separados:

- Leituras: seis serviços e subtotal próprio.
- Vistorias: serviços de vistoria e subtotal próprio, sem Geolocalização.
- Geolocalização: quantidade, preço vigente e subtotal próprio.
- **Vistorias + Geolocalização**: subtotal somente informativo.
- **Bruto = Leituras + Vistorias + Geolocalização**, sem adicionar outra vez o subtotal informativo.

Quantidades são de cobranças por serviço. Impressão, apontamento e feriado podem acumular sobre uma mesma leitura. Não há soma dessas quantidades apresentada como fornecimentos distintos ou registros operacionais.

Os valores vêm dos agregados reais já utilizados pelo aplicativo. O adaptador de Leituras acrescenta o detalhamento à mesma consulta, sem uma nova varredura. A composição reaproveita quantidades/tarifas e verifica cada subtotal contra os indicadores. Quando uma categoria utiliza preços específicos diferentes, exibe as quantidades por preço; não inventa preço médio nem utiliza a tarifa-base para substituir valores reais.

O código contratual de Geolocalização não foi confirmado no cadastro original. O identificador interno `geo` é explicado como tal e não apresentado como código contratual inventado.

Fotografias antigas não são regravadas. Se faltarem os serviços de Leituras na fotografia, utiliza suas quantidades congeladas e os preços da competência fechada, apenas se o subtotal coincidir. Sem essa comprovação, mantém o total histórico e sinaliza detalhes indisponíveis, sem presumir quantidades ou preços.

## Prévia em PDF e Excel

Clique **Gerar relatório de prévia** e escolha PDF, Excel ou ambos. Não exige aprovação, documento, assinatura ou justificativa. O relatório é identificado como **PRÉVIA — NÃO APROVADA**, mesmo quando se baseia em componentes já aprovados: a exportação gerencial não constitui uma nova aprovação.

PDF: identificação Gestão de Medição Sabesp, competência, resumo, composição por componente e serviço, subtotais, bruto e observações de pendências. Excel: **Resumo Geral**, **Serviços de Leituras**, **Serviços de Vistorias** e **Geolocalização**, com valores em reais e subtotais separados. Nenhum relatório soma o subtotal informativo novamente.

A glosa e o líquido simulados aparecem somente se o controle de 1% estiver ativo. A exportação não registra multa nem modifica o status dos fechamentos. O mecanismo definitivo e o relatório oficial anteriores continuam separados e preservados.

PDF/Excel não são gerados ao abrir a página, abrir a composição ou alternar a simulação. A geração recebe apenas os agregados e não acessa registros individuais, banco ou planilhas originais. Os arquivos ficam em sessão; downloads anteriores são ocultados quando mudam competência, dados, formato ou simulação, evitando uma prévia desatualizada. O resumo opcional municipal não foi acrescentado, pois não é necessário para estes pedidos e exigiria consultas adicionais.

## Segurança e testes

Não há novos campos, índices, tabelas ou migrações. Os únicos ajustes na persistência são suporte a propostas de preços em lote, com a mesma transação, auditoria e validação de vigência já existentes, e metadados para detalhar os totais. Nenhuma regra de medição, elegibilidade, preço ou glosa definitiva foi alterada.

Os testes utilizam bancos temporários. Cobrem edição/inclusão/desativação, confirmação de desativação, rollback integral de lote inválido, vigência, histórico, preço específico TSS, dez serviços, subtotais separados, ausência de dupla contagem, exportações PDF/Excel, simulação sem gravação, invalidação dos downloads, ausência de geração automática e preservação dos bancos ao abrir a tabela. Resultados medidos estão em `measurements/price-reports` e no relatório de validação.

Os testes leem o texto do PDF com `pypdf`, dependência **somente de desenvolvimento**, declarada em `requirements-dev.txt`. Para usar o aplicativo e exportar PDFs, continuam valendo as mesmas dependências de antes. Não é necessário instalar essa dependência de testes na atualização normal.

## Atualizar Windows

1. Pare o Streamlit com Ctrl+C.
2. Faça cópia completa de `data` e do código atual para backup, preservando todos os backups anteriores.
3. Extraia o pacote consolidado em uma pasta temporária. Atualize o código, mantendo **`data`, `.venv`, `.streamlit` e backups**. Não exclua arquivos ou reimporte Excel.
4. Para instalação via Git na branch `codex/sistema-fechamento-pr`, use `git fetch origin` e `git pull --ff-only`, sem descartar alterações locais.
5. Execute na pasta do aplicativo:

```bat
.venv\Scripts\python.exe -m streamlit run app.py
```

Não precisa reinstalar Python nem instalar dependências para usar esta versão. Não há migração nova a partir de `5ba82eb`; instalações anteriores à versão financeira 2 mantêm o procedimento anterior de backup/migração, descrito em `ESCOPO_CONTRATUAL_VISTORIAS.md`. Não é necessário instalar versões intermediárias.

Código de aplicação alterado: `contract_finance.py`, `contract_ui.py`, `inspection_billing.py` e `inspection_module_ui.py`. Novos auxiliares indispensáveis: `inspection_price_editor.py` (tabela), `contract_presentation.py` (composição/simulação compartilhada) e `contract_reports.py` (PDF/Excel). Menu, importação, motores de Leituras/feriados, regras de escopo/OS e páginas operacionais não foram modificados. Também são entregues testes, benchmark, documentação e requisitos opcionais de testes.
