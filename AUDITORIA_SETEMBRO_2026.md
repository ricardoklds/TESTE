# Auditoria do fechamento de setembro/2026

## Comprovado com os números fornecidos

Os dois faturamentos informados são reproduzidos exatamente pelas quantidades e
preços fornecidos. A diferença está distribuída assim:

| Serviço | Manual informado | Aplicativo informado | Diferença de quantidade | Diferença de valor |
| --- | ---: | ---: | ---: | ---: |
| Leitura R$ 1,38 | 303.350 | 303.203 | 147 | R$ 202,86 |
| Leitura R$ 1,37 | 2.680 | 2.680 | 0 | R$ 0,00 |
| Leitura R$ 1,28 | 69.161 | 68.972 | 189 | R$ 241,92 |
| Feriado R$ 1,05 | 19.955 | 19.951 | 4 | R$ 4,20 |
| Impressão R$ 0,50 | 79.466 | 78.546 | 920 | R$ 460,00 |
| Apontamento R$ 0,50 | 50.808 | 49.824 | 984 | R$ 492,00 |
| **Total** | **R$ 596.910,43** | **R$ 595.509,45** | — | **R$ 1.400,98** |

Isso comprova a aritmética, **não a correção de um dos fechamentos**. Quantidades
iguais também não comprovam igualdade dos registros individuais. Não há evidência
para acrescentar valores ou selecionar automaticamente linhas faltantes.

## Limitação da base disponível

No ambiente Codex existe somente outubro/2026, com 19.668 registros. **A base real
de setembro com os 20 grupos não está disponível.** Os 1.606 registros sem data,
19.951 feriados cobrados e zero pendências são informações do usuário, não números
reproduzidos aqui. O relatório executado neste ambiente informa `available: false`.

Foi entregue `auditoria_fechamento.py`, para executar na base Windows. Ele abre o
SQLite em **mode=ro**, dentro de uma transação de leitura. Não executa migrações,
UPDATE, reimportação, exclusão, confirmação de localidade ou alteração do fechamento.
Não inclui vistorias ou novos filtros na interface. Os únicos arquivos criados são
os relatórios em pasta nova e uma base temporária de diagnóstico, fora de `data`.

## O que será conferido na base real

### Datas

A aba **Datas a conferir** distingue: coluna não mapeada/ausente, data vazia,
fórmula, número/serial sem conversão aceita, data inválida, data fora do mês e data
interpretável pela projeção cujo formato é rejeitado pelo motor das cinco regras.
Preserva o valor original, ID, arquivo/linha, grupo, município/ATC, funcionário,
fornecimento, execução, erros, unidades e justificativas.

O contador `all_missing_projected_date` reproduz as linhas com `day IS NULL`,
incluindo excluídos; `active_missing_projected_date` separa as ativas. O número
1.606 deve ser comparado com esses dois campos, sem presumir equivalência.

Pelo código existente, data **vazia** pode continuar nas cinco categorias do mês
acumulado, mas não recebe feriado sem uma data interpretável. Datas **inválidas ou
fora do mês** podem gerar erros e zerar as cinco unidades. Outros erros também
podem zerá-las. A apuração de feriado é independente: não impõe filtro de impressão.
Esses são comportamentos auditados, sem mudança de regras. A ferramenta não converte
seriais nem presume uma data para melhorar o faturamento.

### Importações e duplicidades

São comparados arquivos/abas, SHA-256, cabeçalhos, linhas não vazias dos originais,
registros salvos, eventos de importação e fingerprints. A aba **Originais e ignorados**
identifica repetições idênticas e linhas cujo fingerprint está em outro arquivo,
ou sem correspondente no mês. Os originais são somente lidos.

Os eventos antigos não registram cada ID/linha ignorada e podem não identificar
uma aba individual. Por isso, a relação com outro arquivo comprova o **estado atual**,
sem reconstruir por suposição toda a decisão histórica. O histórico existente é
exportado para conferência, sem reescrita. Arquivos ausentes ou com hash divergente
são sinalizados; não se afirma que originais foram verificados com sucesso nesses casos.

**Duplicidades** distingue fingerprint ativo, chave de negócio e fornecimento/data
interpretada/execução. IDs completos são exportados em outra aba, sem truncar uma
lista longa em uma célula. Duplicidade é indicação para revisão; nada é excluído.

Vinte arquivos não comprovam vinte grupos completos. A ferramenta lista grupos
ativos, rótulos 01–20 ausentes quando reconhecíveis e totais por grupo. Sem uma
quantidade esperada por grupo ou os originais completos, não declara completude.

### Seis regras e resultados

Cada registro tem unidades e justificativas das seis categorias. As cinco primeiras
são comparadas com o resultado salvo e a execução somente em memória do motor
original. O total auditado usa os **valores unitários do mês** e as projeções SQL
efetivamente usadas pelo aplicativo, não os números manuais.

São sinalizadas diferenças de unidades, flags, fingerprint, data, identidade do
adicional, projeções ausentes e projeções sem registro original. O total SQL é
comparado à soma detalhada; uma divergência é relatada, nunca corrigida. Preços da
base diferentes dos preços informados também ficam evidentes.

**Não contabilizados** reúne registros excluídos, com erros, zerados ou divergências.
As demais razões por categoria ficam na aba Registros: um registro pode ser correto
em uma categoria e não elegível nas outras. Valores positivos não significam que
todas as seis categorias devessem ser cobradas nessa linha.

### Feriados e as quatro leituras

A aba **Feriados** confere cada leitura separadamente: data, localização, fornecimento,
execução, retida, causa, impressão, unidade cobrada e motivo. Os IDs cobrados são
obtidos da consulta existente; meses fechados preservam os IDs financeiros congelados.
São exportados calendário, histórico e resumo por motivo.

Zero pendências não comprova que todas as leituras receberam adicional: data ausente,
retida Sim, causa preenchida, ausência de feriado, outra abrangência e duplicidades
podem produzir zero cobrança. Impressão não é filtro do feriado; domingos permanecem
sem cobrança automática. A classificação de Bocaina corrigida não acrescenta adicional.

**Sem a lista manual de fornecimento + data + execução, não se pode apontar quais
quatro leituras faltam.** O Excel oferece as linhas de conferência para cruzamento;
não escolhe quatro registros para atingir o valor manual.

## Executar no Windows sem perder dados

1. Feche o Streamlit e mantenha-o fechado até terminar a auditoria. Isso evita
   alterações concorrentes e disputa de escrita com a transação longa de leitura.
2. Mantenha a cópia externa habitual de `data` e do programa, conforme
   [BACKUP_RECOVERY.md](BACKUP_RECOVERY.md). Não há migração nesta entrega.
3. Copie os arquivos de código/documentação/testes atualizados para a instalação,
   incluindo `auditoria_fechamento.py`. Preserve **data, .venv, originais e backups**.
   Não reinstale Python e não reimporte planilhas.
4. No PowerShell da instalação:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_auditoria.py -v
.\.venv\Scripts\python.exe auditoria_fechamento.py --data data --output auditoria-setembro-2026
```

Se o banco estiver no caminho configurado por `APP_DATA_DIR`, passe esse caminho
em `--data`. A pasta `--output` deve ser **nova e fora de data**; a ferramenta recusa
sobrescrever auditoria anterior. Reserve disco para XML/Excel e diagnóstico temporário.
O XLSX é escrito incrementalmente, em abas divididas no limite do Excel. Pode levar
minutos; as mensagens mostram os registros e arquivos conferidos. Não se carregam
todos os registros em listas Python para agrupar: agregações e índices ficam na
base temporária de diagnóstico. O desempenho Windows/400 mil não foi medido aqui.

Por padrão, os originais Excel são conferidos. `--sem-originais` evita reler esses
arquivos, mas reduz a cobertura da integridade e das linhas ignoradas; essa limitação
fica registrada. A leitura de um XLSX mantém os bytes daquele arquivo em memória,
não de todos os arquivos juntos.

Ao aparecer **Auditoria concluída**, serão gerados:

- `RELATORIO.md`: evidências, hipóteses e resumo da base.
- `resultado.json`: totais, divergências, grupos, importações, datas, preços,
  hashes do código de auditoria e indicação explícita de disponibilidade da base.
- `auditoria.xlsx`: comparação, registros, datas, não contabilizados, feriados,
  agregações, duplicidades, originais, calendário e histórico.

Se a execução falhar, não considere uma pasta parcial como auditoria concluída.
Mantenha-a e execute novamente com outro nome após identificar o erro; o banco
permanece somente leitura. Se `available` for falso, confira o caminho da base:
o fechamento real não foi auditado. Não execute o programa sobre um banco anterior
ao schema 5: ele recusa migrar.

## Hipóteses a verificar, sem concluir previamente

- Datas inválidas, fora do mês ou formatos rejeitados podem explicar parte dos
  registros zerados. Datas vazias, sozinhas, não provam exclusão do mês acumulado.
- Duplicatas ignoradas, exclusões lógicas, filtros usados na leitura do painel ou
  preço do mês podem explicar divergências; dependem das evidências da base.
- Impressão é soma de quantidades, não contagem de células. Apontamento conta
  preenchimento normalizado, inclusive zero; espaços e fórmulas merecem conferência.
- Os quatro feriados podem envolver datas, abrangência, domingo, retida, causa,
  identidade ou duplicidade. Não se assume qual desses motivos ocorreu.

Nenhuma hipótese foi aplicada ao fechamento. As seis regras, preços e módulos de
produção permanecem intactos nesta entrega.

## Validação da ferramenta

**65 testes passaram**, incluindo datas vazias/inválidas/fora do mês e formato ISO
fracionário, originais/fingerprints ignorados, somas das seis categorias, snapshots
fechados, exclusão/restauração, projeções órfãs e recusa de saída dentro de data ou
sobrescrita de auditoria anterior. Os testes usam bancos temporários; não representam
a análise dos 20 grupos de setembro. Banco, originais e backups de produção ficaram
byte a byte iguais. Evidências em `measurements/auditoria-setembro/`.
