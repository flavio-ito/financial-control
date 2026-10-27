# Etapa 0 — auditoria e plano de execução da V1

Data: 2026-10-21. Escopo: `PRODUCT_ROADMAP.md`, Etapa 0 e V1. O repositório continha alterações locais antes desta auditoria; elas foram preservadas. Nenhum banco de usuário foi aberto ou apagado.

## Estado observado

Frontend React 18/TypeScript/Vite com React Query, React Hook Form, Zod e testes Vitest. Backend FastAPI/SQLAlchemy/SQLite, migrações Alembic 0001–0007, testes pytest e launcher Windows. `scripts/build_windows.ps1` gera tipos OpenAPI, roda testes, compila e empacota. `README.md`, `docs/modelo-dados.md`, `docs/arquitetura.md`, `docs/guia-usuario.md` e `docs/migracao-recuperacao.md` descrevem instalação e regras.

| Função auditada | Estado | Evidência |
| --- | --- | --- |
| Contas, saldo inicial e saldos | Implementada e funcional | `storage/models.py`, `domain/services.py`, `test_financial_services.py` |
| Cartões, limites, parcelas e faturas | Implementada e funcional | `domain/card_commitment.py`, `test_domain_calculations.py` |
| Lançamentos, transferências e categorias | Implementada e funcional | `domain/services.py`, `test_business_api.py` |
| Recorrências e orçamentos | Implementada e funcional | `domain/recurrence.py`, `domain/analytics.py`, `test_planning_and_history.py` |
| Previsto versus realizado, dashboards e alertas | Implementada e funcional no escopo existente | `domain/states.py`, `domain/analytics.py`, `OverviewPage.tsx` |
| CSV, OFX, prévia, deduplicação e conciliação | Implementada e funcional no escopo documentado | `integrations/files.py`, `integrations/service.py`, `test_bank_imports.py` |
| Regras configuráveis de categoria | Não implementada na revisão inicial | Nenhum modelo/rota para regras; categoria era escolhida manualmente na revisão |
| Primeiro uso | Implementada com inconsistência | `SetupPage.tsx` criava cartões com limite zero e datas fixas não informadas |
| Backup, restauração, exportação, verificação | Implementada e funcional | `maintenance/backup.py`, `api/backup_routes.py`, `test_backup.py` |
| Offline, segurança local e pacote Windows | Implementada e funcional pelos testes existentes | `launcher`, `api/security.py`, `test_security.py`, `scripts/test_packaged.ps1` |

## Riscos e decisões

- Dupla contagem: transferências têm duas pernas, mas ficam fora de receita/despesa; compra gera obrigação no cartão e pagamento de fatura gera saída de caixa sem nova despesa de consumo. Importados passam por revisão antes de criar fatos.
- Dinheiro: centavos inteiros e limites seguros em API e banco. Datas financeiras são civis; instantes técnicos usam UTC. Parcelas têm rateio exato testado.
- Edição e exclusão: vínculos históricos são preservados, estados e reversões evitam remoção silenciosa. Correção externa reabre revisão sem sobrescrever lançamento local.
- Migração e backup: alterações estruturais são aditivas. O launcher faz backup antes de migrar; testes usam bancos temporários. A V1 não modifica banco real.
- Limitação existente: OFX aceita subconjunto documentado; CSV sem ID estável deduplica pelo arquivo e posição, então arquivos sobrepostos exigem revisão. A sugestão por valor/data não prova duplicidade.

## Plano e dependências

1. Etapa 1: preservar o domínio existente; corrigir apenas os valores inventados no cadastro de cartões. Arquivos: `SetupPage.tsx`, `AccountsPage.tsx`, teste de primeiro uso.
2. Etapa 2: reutilizar importação e conciliação existentes; adicionar regras opcionais de expressão na descrição com destino opcional e sugestão explícita. Arquivos: modelo, migração 0008, serviço/rotas de integrações, interface e testes. Nenhuma regra grava categoria automaticamente.
3. Etapa 3: confirmar primeiro uso, backup, offline, segurança e pacote existente; documentar limites e resultados. Não alterar fluxos já aprovados sem evidência de falha.

Estratégia de testes: baseline, testes direcionados por etapa, suíte completa backend/frontend, typecheck e build. A migração deve ser verificada em banco temporário vindo da revisão anterior; dados financeiros anteriores devem permanecer. O relatório de execução está em `docs/V1_REPORT.md`.

## Checklist

- [x] Etapa 0: estrutura, dependências, fluxos, riscos e baseline auditados.
- [x] Etapa 1: domínio preservado; cadastro de cartão corrigido e testado.
- [x] Etapa 2: importadores existentes reutilizados; sugestões configuráveis implementadas e testadas.
- [x] Etapa 3: regressão, build, autoteste e smoke completo do pacote; resultados registrados.
