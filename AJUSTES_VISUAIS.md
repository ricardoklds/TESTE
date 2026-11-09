# Ajustes de interface — competência mensal e navegação

Esta atualização modifica somente três arquivos do aplicativo:

- `app.py`: espaço superior de 4,5 rem para evitar sobreposição do cabeçalho; cores azuis nos expansores, campos e botões da barra lateral; espaçamento compacto.
- `navigation.py`: opção Produtividade de Vistorias e seleção de mês/ano imediatamente abaixo de Configurações. Internamente retorna sempre o primeiro dia do mês e mantém a competência `AAAA-MM` das consultas existentes. O padrão continua outubro/2026.
- `inspection_module_ui.py`: página de produtividade por município com tabela e gráfico, usando os agregados financeiros existentes e o mesmo cache. Não consulta registros individuais. Se a fotografia histórica não contém municípios, utiliza a consulta agregada já existente. Geolocalização não integra o faturamento dessa página.

Não foram alterados preços, classificações, regras, consultas financeiras, importações, modelos de dados ou migrações. Municípios ausentes aparecem como não informados; não é atribuído funcionário por suposição. Os controles de dia e intervalo das telas de Leituras permanecem disponíveis.

## Verificação

Testes automatizados utilizam somente bases temporárias. Os testes existentes foram adaptados exclusivamente para selecionar mês e ano no lugar do antigo calendário diário da barra lateral. Os novos testes verificam ida e volta entre competências, igualdade financeira e integridade dos arquivos SQLite de teste; também impedem consultas adicionais ao abrir a produtividade com o cache já preenchido e conferem suas quantidades e valores contra os agregados existentes.

A suíte completa passou em 163 testes. Não houve diferenças financeiras nas verificações de regressão. A base real de setembro do computador do usuário não foi utilizada nem modificada. Verificação adicional em Chromium local: cabeçalho visível, fundos azuis dos expansores inclusive ao passar o mouse, navegação para produtividade e ausência de erro Streamlit em desktop e tablet. A nova página utiliza o cache existente; não foi realizado benchmark de milhões de registros nesta atualização visual.

## Atualização no Windows

1. Encerre o Streamlit (Ctrl+C no terminal).
2. Faça uma cópia de segurança da pasta do sistema.
3. Substitua somente `app.py`, `navigation.py` e `inspection_module_ui.py` pelos arquivos desta versão. Mantenha os três juntos, pois a navegação usa o novo seletor mensal.
4. Preserve `data`, `.venv`, backups, configurações locais e planilhas originais. Não reimporte arquivos. Não é necessário instalar Python ou atualizar dependências.
5. Na pasta do aplicativo, execute:

```powershell
.venv\Scripts\python.exe -m streamlit run app.py
```

Para voltar à versão anterior, restaure os mesmos três arquivos da cópia de segurança. Não é necessária restauração do banco para esta atualização.
