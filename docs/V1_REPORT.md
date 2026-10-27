# Relatório técnico — V1

Data inicial: 2026-10-21. Atualização do importador CSV: 2026-10-25. Escopo: Etapa 0 e Etapas 1–3 da V1 do `PRODUCT_ROADMAP.md`. Alterações locais preexistentes foram preservadas. Nenhum commit, push ou publicação foi feito.

## A. Funcionalidades entregues

- Mantidos os fluxos existentes de contas, lançamentos, transferências, cartões, parcelas, faturas, orçamentos, recorrências, CSV/OFX, conciliação, backup, restauração e operação local.
- Cadastro de cartão passa a pedir limite, dia de fechamento e dia de vencimento no primeiro uso e na criação pela página de contas; não cria valores silenciosos.
- Regras configuráveis de sugestão de categoria por trecho da descrição, com escopo opcional de conta ou cartão. Prévia e revisão mostram sugestões; só a confirmação explícita cria lançamento categorizado. Regras podem ser desativadas sem reclassificar dados anteriores.
- Leitura automática de CSV com detecção de codificação, separador, colunas e formatos conhecidos. O usuário revisa o mapeamento, pode corrigi-lo e gera outra prévia antes da confirmação.
- Faturas Nubank com colunas `date`, `title` e `amount` sugerem inversão explícita de sinais quando importadas para cartão; a regra aplicada fica vinculada à assinatura da prévia.
- A confirmação de CSV/OFX cria imediatamente os lançamentos classificados como novos. Correspondências são separadas em um bloco de atenção e exigem a escolha entre conciliar o registro existente ou inserir outro. Créditos de cartão podem criar estorno após a seleção de uma compra compatível.
- Antes da segunda etapa do modal, o backend compara o destino escolhido com sinais confiáveis do arquivo e bloqueia combinações incompatíveis, como transferência Pix destinada a cartão ou fatura Nubank destinada a conta.
- Resumo do primeiro uso orienta o cadastro opcional de recorrências e a importação de extratos.

## B. Modificações

- `docs/IMPLEMENTATION_PLAN.md`: auditoria, classificação de funções, riscos, plano e checklist.
- `frontend/src/pages/SetupPage.tsx`, `AccountsPage.tsx` e teste de primeiro uso: dados reais do cartão no cadastro.
- `backend/app/storage/models.py` e migração `0008_import_category_rules.py`: tabela aditiva de regras.
- `backend/app/integrations/service.py` e `backend/app/api/integrations.py`: correspondência determinística, CRUD de regras e sugestões na prévia/revisão.
- `frontend/src/components/BankIntegrations.tsx` e `StatementImportModal.tsx`: gestão e apresentação das sugestões.
- `backend/tests/test_bank_imports.py`, `test_schema.py`, `test_backup.py`: regressão de regras, API, migração e nova revisão.
- `frontend/src/api/schema.d.ts`: tipos OpenAPI regenerados.
- `.gitignore`: assets compilados em `backend/app/static` permanecem fora do controle de versão.
- `scripts/test_packaged.ps1`: aceita diretório de dados de smoke separado, preservando artefatos anteriores.
- `docs/modelo-dados.md` e `arquitetura.md`: contrato e instruções atualizados.

## C. Arquitetura e integridade financeira

A migração 0008 só adiciona `import_category_rules`, com FKs restritivas para categoria e destino. O motor compara texto sem diferenciar acentos ou maiúsculas e devolve todas as regras compatíveis. Na importação local, uma única sugestão é aplicada na confirmação; sugestões ambíguas não categorizam o lançamento. A confirmação de CSV/OFX grava evidência importada e fato financeiro na mesma transação, enquanto duplicidades exatas são ignoradas e correspondências dependem da decisão exibida na prévia. Saldos, contas, faturas, parcelas e lançamentos históricos não foram migrados nem reescritos.

## D. Interface

O assistente e o formulário de cartões exibem campos de limite e calendário. Integrações bancárias oferece cadastro e desativação de regras. A importação usa três etapas intituladas **Importar arquivo**, **Alguns arquivos podem já estar salvos no banco de dados** e **Visualização prévia**. A segunda etapa orienta a conferência das correspondências e apresenta uma única vez os cabeçalhos do dado importado, correspondente no banco e ação; cada linha permite **Salvar** ou **Ignorar**. Essa tabela segue as superfícies brancas, bordas neutras, cabeçalho verde acinzentado e botões já usados no restante da aplicação. A terceira etapa mostra inicialmente apenas a tabela e as duplicações; **Editar** abre abaixo dela o painel de leitura automática e mapeamento de colunas. A etapa também oferece **Salvar** ou **Voltar**. O modal de importação usa largura ampliada no desktop para exibir a tabela completa sem rolagem horizontal. Estornos ainda exigem a seleção da compra original. Todos os modais apresentam um controle “×” no canto superior direito no lugar do botão visual “Cancelar”, preservando o nome acessível da ação.

## E. Validação executada

| Etapa | Comando/verificação | Resultado |
| --- | --- | --- |
| 0 — baseline | `.venv\\Scripts\\python.exe -m pytest backend/tests -q` | 111 passaram, 1 aviso de dependência |
| 0 — baseline | `npm.cmd test --prefix frontend -- --run`; `npm.cmd run typecheck --prefix frontend` | 19 passaram; tipagem aprovada |
| 1 — cartão | testes frontend e typecheck após correção | 19 passaram; tipagem aprovada |
| 2 — importação | `pytest backend/tests/test_bank_imports.py backend/tests/test_schema.py backend/tests/test_backup.py -q` | 36 passaram, 1 aviso |
| 3 — regressão | `.venv\\Scripts\\python.exe -m pytest backend/tests -q` | 116 passaram, 1 aviso de dependência |
| 3 — interface | `npm.cmd test --prefix frontend -- --run`; `npm.cmd run typecheck --prefix frontend`; `npm.cmd run build --prefix frontend` | 20 passaram; tipagem e build aprovados |
| Ajustes do importador | `.venv\Scripts\python.exe -m pytest backend/tests -q`; `npm.cmd test --prefix frontend -- --run`; typecheck e build | 120 backend e 22 frontend passaram; tipagem e build aprovados |
| 3 — exemplos CSV | análise e parsing local dos dois arquivos fornecidos em 2026-10-25 | extrato de conta: 28 linhas, mapeamento completo, sem inversão; fatura Nubank: 18 linhas, preset reconhecido, inversão aplicada; nenhum lançamento persistido |
| 3 — API | `scripts/generate_api_types.ps1` | OpenAPI e tipos gerados |
| 3 — pacote | PyInstaller com saída isolada em `build/v1-check-dist`, seguido de `ControleFinanceiroLocal.exe --self-test` com diretório de dados novo | build aprovado; autoteste retornou `status: ok`, 1 conta, 1 pagamento e FKs ativas |
| 3 — smoke Windows | `scripts/test_packaged.ps1 -PackageDirectory dist\\v1-check -SmokeDataDirectory build\\v1-packaged-smoke-20261021` | `PACKAGED_SMOKE_OK`: inicialização, health, SPA, 404, instância única e banco fora do pacote |

## F. Pendências e limites

- O pacote de validação foi colocado em `dist/v1-check` e testado com dados temporários próprios. O ZIP de distribuição habitual não foi sobrescrito nem publicado.
- Migrações e importações foram testadas com dados sintéticos temporários.
- OFX aceita o subconjunto documentado. CSV sem identificador estável usa arquivo e posição; extratos sobrepostos exigem revisão. Sugestões de categoria podem ser ambíguas e exigem escolha humana.
- O build Vite emitiu aviso de tamanho do bundle; não impediu a compilação.

## G. Continuação

A V1 está validada por testes automatizados, autoteste e smoke completo do pacote. Uma futura V2 deve começar pela análise separada do motor de projeções existente, sem misturar previsões com lançamentos realizados. Nenhuma implementação de V2 foi feita nesta execução.
