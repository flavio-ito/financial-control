# Changelog

## 0.1.0 — MVP concluído (2026-09-09)

### Etapa 1 — Fundação local

- React/Vite, FastAPI/Uvicorn, SQLite/SQLAlchemy/Alembic, APP_ID estável, sessão local, CSRF, instância única e fallback SPA.

### Etapa 2 — Modelo e persistência

- Schema completo com 22 tabelas, constraints, índices, revisões, idempotência, estados e operações atômicas.

### Etapa 3 — Domínio financeiro

- Contas, caixa, transferências, compras, parcelas, faturas, pagamento, estorno, reembolso, crédito e compras antigas.

### Etapa 4 — Planejamento

- Compras planejadas, recorrências versionadas, exceções mensais, ocorrências e planos de pagamento.

### Etapa 5 — Orçamento e análise

- Painel consolidado, orçamento realizado/projetado, cobertura temporal e prevenção de dupla contagem.

### Etapa 6 — Interface

- Onboarding persistente e telas responsivas para todos os fluxos do MVP, com datas e moeda pt-BR.

### Etapa 7 — Dados e recuperação

- Backup `.finbackup`, manifesto SHA-256, retenção diária, prévia de restauração e rollback automático.

### Etapa 8 — Distribuição

- Executável Windows autocontido, autoteste embarcado, smoke sem runtimes externos e ZIP de entrega.
