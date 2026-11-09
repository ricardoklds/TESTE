# Atualização de interface — Gestão de Medição Sabesp

Esta etapa simplifica a navegação, Geolocalização e a visualização do Fechamento Geral. Não altera critérios de Leituras, cobrança única por OS, escopo de Vistorias, meta de 99%, feriados ou preços. Não acrescenta tabelas, índices, migrações ou dependências. Os testes e medições usam apenas bancos temporários.

## Menu

A caixa de seleção de módulos foi removida. Clique nos cabeçalhos **Leituras**, **Vistorias** e **Configurações** para abrir ou recolher suas opções. A expansão ocorre no navegador e não executa consultas Python. Painel Geral e Fechamento Geral têm botões diretos. Somente a página escolhida é renderizada; abrir um grupo não carrega seus relatórios.

As seis páginas operacionais de Vistorias ficam no respectivo grupo. Edição administrativa centralizada em:

- **Configurações → Serviços e Preços de Vistorias**: preços, categoria TSS, enquadramento faturável/não faturável/pendente, vigência, prévia de impacto e histórico.
- **Configurações → Municípios do Contrato**: lista de escopo e histórico já existentes.
- **Configurações → Regras comerciais de Vistorias**: critérios por OS/execução/conferência, vigência, impacto e histórico.
- **Configurações → Configurações de Leituras**: acesso mantido para preservar a edição existente de feriados e preços de Leituras.

Os preços iniciais permanecem: Aprovação R$22,50; Predial R$22,50; Cadastral R$12,00; Geolocalização R$12,00. Cadastros já existentes não são substituídos por esses valores. As proteções contra alteração retroativa de competências aprovadas e a confirmação de impacto de mudanças comerciais continuam funcionando.

## Geolocalização

Escolha a competência no menu lateral. Na página informe **Quantidade**, veja o **Preço unitário vigente** e o **Valor total**, e clique **Salvar**. O total atualiza após editar o campo, sem precisar salvar. Não há campo obrigatório de documento, justificativa ou confirmação adicional.

Nenhuma quantidade é presumida. Campo vazio não salva; zero pode ser informado explicitamente. Quantidades devem ser inteiras e não negativas. O registro de auditoria guarda automaticamente data/hora UTC, mês, lançamento anterior e novo. A anotação interna de lançamento manual não é apresentada como documento comercial.

O detalhamento fica em **Detalhar por município (opcional)**. Escolha **Por município** e preencha uma linha `Município;quantidade`, por exemplo `BOCAINA;2`. O preço e o total usam o mesmo cálculo da quantidade salva. Municípios fora do escopo não entram na cobrança; desconhecidos permanecem pendentes e não são autorizados automaticamente.

**Um único modo é principal por competência.** Salvar substitui somente o lançamento de Geolocalização daquele mês; não cria parcelas cumulativas nem soma total mensal ao detalhamento municipal. Ao mudar de modo e salvar, o lançamento anterior, incluindo detalhes municipais, permanece no histórico. A quantidade total mensal deve representar o contrato: não se inventa discriminação municipal para um total informado sem detalhes.

Competências aprovadas continuam bloqueadas para edição, inclusive pela API. A tarifa respeita sua vigência. Nenhum fechamento aprovado é recalculado por uma edição futura.

## Fechamento Geral e simulação

A tela mostra **Leituras + Vistorias + Geolocalização = Fechamento bruto**. O detalhamento por categoria está em uma seção expansível, com cabeçalhos em português e valores em reais.

O controle **Aplicar multa de 1%** atua somente na visualização gerencial:

- Desligado: glosa simulada zero e líquido simulado igual ao bruto.
- Ligado: glosa simulada de 1% sobre o bruto completo e líquido estimado.
- Desligar retira o desconto imediatamente. Não pede documentação ou confirmação e não grava multa, histórico ou fotografia de fechamento.

A simulação usa aritmética exata em centavos e arredondamento comercial para o centavo. É independente da meta de 99%: permite análise gerencial sem decidir se a aplicação definitiva seria contratualmente cabível. Cada competência tem seu próprio controle de sessão; o valor simulado não é persistido no banco.

O mecanismo definitivo permanece separado em **Registro definitivo de glosa · fechamento oficial**, disponível para fechamentos validados e sujeito às condições e confirmações anteriores. Uma glosa definitiva existente não é apagada ou aplicada novamente ao ligar/desligar a simulação. O líquido oficial aparece nessa seção; o líquido principal da simulação, quando desligada, é o bruto, conforme solicitado.

O relatório do contrato continua exportando os valores oficiais, sem incorporar a glosa simulada. Suas colunas monetárias agora estão em reais e formatadas como moeda; não confunda esses valores com os centavos usados internamente.

## Testes e desempenho

A suíte completa passou: **140 testes em 48,065s**. Foram adicionados oito testes da experiência simplificada, incluindo hashes dos bancos antes/depois da simulação, bloqueio de consultas financeiras pesadas ao alternar, preservação de glosa definitiva, Geolocalização sem documento, não duplicação, escopo, vigência, mês aprovado e exportação oficial. Os testes existentes foram adaptados aos botões do menu, preservando as verificações financeiras. Após os ajustes finais de apresentação, os testes de interface e editor foram executados novamente; logs em `measurements/simple-interface`.

Benchmark isolado: **500.000 Leituras + 100.000 Vistorias sintéticas**, comparação com `529185c`. Tempos reais medidos em segundos:

| Operação | Antes | Depois |
|---|---:|---:|
| Painel de Leituras em cache, mediana de 3 | 0,019 | 0,018 |
| Primeira entrada em Vistorias | 1,692 | 1,602 |
| Retorno a Leituras | 0,019 | 0,022 |
| Primeira abertura do Fechamento Geral | 2,035 | 2,095 |
| Fechamento Geral em cache, mediana de 3 | 0,007 | 0,010 |
| Abrir Geolocalização | 0,051 | 0,007 |
| Salvar quantidade de Geolocalização | 0,011 | 0,010 |
| Alternar simulação, mediana de 4 | Não existia | 0,009 |

Os componentes financeiros e as seis quantidades de Leituras coincidiram nas duas versões. O SHA-256 do banco de Leituras permaneceu igual. Alternar a simulação preservou os hashes de todos os bancos temporários. Pico de RAM do processo completo: 886,46 MiB antes e 868,64 MiB depois; inclui Streamlit e todas as páginas exercitadas, não apenas o controle de glosa.

Os testes AppTest medem o servidor, não navegador/rede ou importação Excel nesse volume. A expansão nativa do menu não é cronometrada por AppTest. Pequenas diferenças de milissegundos não demonstram ganho ou regressão universal; a primeira abertura do Fechamento Geral continua dependente das consultas iniciais. Não foi executado um novo fechamento real de setembro nem alterada a produção. O benchmark pode ser reproduzido no Linux com `python benchmark_simple_interface.py --output <pasta-nova>` em checkout Git com o commit de referência disponível.

## Atualizar no Windows

1. Pare o aplicativo com **Ctrl+C**.
2. Copie **toda a pasta `data`** e o código instalado para um backup externo. Preserve também todos os backups anteriores.
3. Extraia o pacote atualizado em uma pasta temporária. Copie os arquivos de código e documentação para a instalação, preservando **`data`, `.venv`, `.streamlit` e backups**. Não exclua arquivos nem reimporte planilhas.
4. Para instalação por Git, atualize a branch `codex/sistema-fechamento-pr` com `git fetch origin` e `git pull --ff-only`, sem descartar alterações locais.
5. Não é necessário reinstalar Python ou dependências. Na pasta do sistema:

```bat
.venv\Scripts\python.exe -m streamlit run app.py
```

Não há migração nova entre a versão anterior `529185c` e esta. Se sua instalação ainda antecede a versão financeira 2 de Vistorias, o pacote consolidado mantém a migração anterior com backup consistente verificado; consulte `ESCOPO_CONTRATUAL_VISTORIAS.md` antes da primeira abertura. Não precisa instalar versões intermediárias.

Para voltar de versão, pare o aplicativo e recupere o código e a cópia completa de `data` guardados juntos, preservando a instalação atual separadamente. Não misture um banco antigo com importações posteriores.

Arquivos de aplicação modificados: `app.py`, `navigation.py`, `contract_ui.py`, `inspection_module_ui.py` e `inspection_billing.py`. Também foram atualizados os testes de navegação e adicionados `tests/test_simple_interface.py`, `tests/ui_navigation.py`, `benchmark_simple_interface.py`, esta documentação e as medições. Nenhum Excel original, arquivo de produção, regra de Leituras ou motor de classificação de OS foi modificado.
