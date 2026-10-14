# Backup e recuperação antes de atualizar

Esta otimização não altera a estrutura do banco (permanece versão 5). Não apaga
registros, originais, histórico ou backups. Os ensaios usam exclusivamente bancos
temporários novos. Não é necessário migrar o banco da instalação atual.

Antes de atualizar no Windows:

1. Feche o aplicativo e o terminal Streamlit. Confirme que nenhuma importação ou
   exportação está em execução e que outro usuário não está usando a mesma pasta.
2. Copie **a pasta `data` inteira**, incluindo `contrato.sqlite3`, eventuais arquivos
   `-wal`/`-shm`/`-journal`, `originais`, `backups` e `exports`, para uma pasta de
   backup fora da instalação. Copie também os arquivos atuais do programa.
3. Mantenha essa cópia intacta. Não faça backup de um SQLite em uso por simples
   cópia do arquivo: uma escrita concorrente pode produzir uma cópia inconsistente.
4. Atualize apenas os arquivos do programa. Nunca substitua ou mescle `data` com
   uma pasta extraída de outro computador. Execute os testes em base temporária.
5. Abra o aplicativo e confira os totais de um mês conhecido, importações ativas,
   calendário e histórico. Não descarte o backup depois dessa conferência.

Se houver falha, feche o aplicativo, preserve a pasta com falha com outro nome,
restaure juntos **o programa anterior e a cópia completa de `data`**, e reinicie.
Não misture versões de um banco com seus arquivos auxiliares. Não sobrescreva a
única cópia disponível. Alterações/importações feitas depois do backup não estarão
nele: preserve a pasta com falha para recuperação posterior.

Riscos de futuras migrações: interrupção, espaço insuficiente (banco + backup +
projeções temporárias), bloqueio por outra instância, incompatibilidade entre
versões e erro na projeção de dados. As migrações já existentes criam backup com
SQLite `backup()` e validam `integrity_check` **antes** de alterar a estrutura.
Para uma versão anterior à 5, faça também a cópia externa acima e reserve espaço
para os backups automáticos de cada etapa. Nenhuma migração foi adicionada nesta
entrega. Recuperação foi verificada com bancos sintéticos; não foi executada no
banco de produção.
