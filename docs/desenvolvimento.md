# Guia de desenvolvimento

## Arquitetura

- `backend/app/launcher`: pasta de dados, instância única, migração, servidor e navegador.
- `backend/app/api`: contrato HTTP, sessão local, CSRF, idempotência e erros estáveis.
- `backend/app/domain`: regras financeiras, recorrência, planejamento e analytics.
- `backend/app/storage`: SQLAlchemy, SQLite e unidades de trabalho.
- `backend/app/maintenance`: backup, restauração e autoteste empacotado.
- `frontend/src`: React/TypeScript estrito, interface pt-BR e cliente same-origin.

Dinheiro atravessa a API em centavos inteiros no intervalo seguro do JavaScript. Datas financeiras são civis (`YYYY-MM-DD`); auditoria usa UTC. Alembic é a única autoridade do schema. SQLite opera com foreign keys, busy timeout e transações explícitas; mutações concorrentes também são serializadas no processo.

## Ambiente

O build validado usa Python 3.7.8 por limitação do ambiente atual, Node.js 22 e npm 10. As dependências Python estão fixadas em `requirements.lock`; Python 3.7 está fora de suporte e deve ser atualizado antes de evolução prolongada do produto.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
npm.cmd --prefix frontend ci
```

## Comandos

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm.cmd --prefix frontend test -- --run
npm.cmd --prefix frontend run typecheck
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\generate_api_types.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build_frontend.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Para iniciar sem empacotar:

```powershell
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe -m app.launcher
```

`FINANCAS_DATA_DIR` seleciona uma pasta de dados isolada para desenvolvimento/testes. `FINANCAS_NO_BROWSER=1` impede a abertura automática do navegador. O launcher vincula apenas `127.0.0.1` em porta dinâmica e grava em `runtime.json` somente PID e porta.

## API, banco e pacote

`scripts/generate_api_types.ps1` exporta o OpenAPI do backend e regenera `frontend/src/api/schema.d.ts`. Migrações são aplicadas no startup, após backup preventivo quando existe banco. Alterações SQLite que recriem tabelas devem usar o modo batch do Alembic.

O spec PyInstaller produz uma distribuição `onedir`. `scripts/test_packaged.ps1` executa o binário com um PATH que não contém Python ou Node, roda o autoteste interno, sobe o servidor, verifica SPA/API/instância única e confirma que os dados foram gravados fora do pacote.
