# Arquitetura

## Visão geral

O Controle Financeiro Local é uma aplicação desktop-local distribuída como pacote Windows `onedir`. O executável inicializa um servidor FastAPI exclusivo em `127.0.0.1`, abre a interface React no navegador padrão e mantém os dados em SQLite no perfil do usuário. Não há serviço remoto, nuvem ou integração bancária no MVP.

```text
Navegador
   │ HTTP same-origin + cookie/CSRF
   ▼
Launcher Windows ── Uvicorn/FastAPI ── API /api/v1
                         │                 │
                         │                 ▼
                         │           domínio financeiro
                         │                 │
                         ▼                 ▼
                    SPA React       SQLAlchemy/SQLite
                                          │
                                          ▼
                              migrações e backups locais
```

## Componentes

### Launcher

`backend/app/launcher` é responsável por:

- determinar o diretório de dados;
- impedir uma segunda instância por meio de lock de arquivo;
- executar migrações antes de abrir a aplicação;
- gerar ocorrências recorrentes pendentes;
- criar o backup diário;
- selecionar uma porta local disponível;
- emitir o token bootstrap de uso único;
- iniciar o Uvicorn e abrir o navegador;
- remover `runtime.json`, revogar sessões e fechar o banco ao encerrar.

Falhas de startup são registradas em `startup-error.log` no diretório de dados. `runtime.json` contém somente PID e porta.

### API e frontend

`backend/app/main.py` compõe a aplicação FastAPI, os middlewares, handlers de erro, rotas `/api/v1` e o fallback da SPA. Os assets compilados de `frontend/dist` são copiados para `backend/app/static` durante o build e incluídos no pacote pelo PyInstaller.

`frontend/src` contém a aplicação React/TypeScript. O cliente usa URLs relativas, portanto frontend e API compartilham origem. React Query controla carregamento e invalidação; React Hook Form e Zod tratam formulários e validação de entrada no cliente. A API continua sendo a autoridade de validação e regras de negócio.

### Domínio

`backend/app/domain` concentra cálculos, estados, recorrência, planejamento e análises. Regras que alteram várias entidades são executadas dentro da mesma unidade de trabalho. O domínio não deve depender da apresentação do frontend.

### Persistência

`backend/app/storage` contém modelos SQLAlchemy, engine SQLite, sessões e repositórios. Cada unidade de trabalho confirma integralmente ou faz rollback. O SQLite é configurado com:

- `foreign_keys=ON`;
- `busy_timeout=5000`;
- `check_same_thread=False`;
- lock em processo para serializar mutações financeiras.

Alembic é a única autoridade do schema. Uma mudança estrutural requer nova revisão em `backend/migrations/versions`; revisões publicadas não devem ser reescritas.

### Manutenção

`backend/app/maintenance` implementa backup, validação, restauração e autoteste. Um `.finbackup` contém apenas `database.sqlite3` e `manifest.json`. O manifesto registra versão do formato, versão do aplicativo, revisão Alembic, data UTC, moeda e SHA-256 do banco.

Antes de promover uma restauração, o aplicativo valida estrutura, checksum, moeda, formato, revisão do schema, integridade SQLite e foreign keys. Um backup de segurança é criado antes de substituir o banco atual.

## Inicialização e sessão

1. O launcher adquire o lock de instância.
2. Migra o banco, criando backup prévio quando necessário.
3. Gera recorrências e backup diário.
4. Inicia o servidor em `127.0.0.1` e porta dinâmica.
5. Gera um token bootstrap aleatório e abre `/#bootstrap=...`.
6. O frontend envia o token para `/api/v1/session/bootstrap`.
7. O token é invalidado e substituído por sessão em cookie e token CSRF em memória.
8. Leituras exigem sessão; mutações exigem também Origin e CSRF válidos.

O fragmento da URL não é enviado automaticamente ao servidor pelo navegador. Tokens e sessões não são persistidos no SQLite nem em logs.

## Escrita financeira

O fluxo típico de uma mutação é:

```text
entrada validada
   → autenticação/CSRF
   → lock de mutação
   → validação de revisão, estado e preview
   → serviço de domínio
   → escrita de todos os efeitos
   → auditoria/idempotência
   → commit único ou rollback total
```

Operações sensíveis utilizam preview para apresentar os efeitos antes da confirmação. O preview é derivado do conteúdo e do estado atual; se ficar obsoleto, a API responde com `STALE_PREVIEW`. Operações sujeitas a reenvio usam chave de idempotência persistida por escopo e hash do request.

## Diretórios e artefatos

| Local | Finalidade | Versionado |
| --- | --- | --- |
| `backend/app` | API, domínio, persistência e launcher | Sim |
| `backend/migrations` | Histórico do schema | Sim |
| `backend/tests` | Testes automatizados | Sim |
| `frontend/src` | SPA React/TypeScript | Sim |
| `frontend/src/api/schema.d.ts` | Tipos gerados do OpenAPI | Sim |
| `backend/app/static` | SPA compilada para empacotamento | Não |
| `build` | Intermediários de geração e PyInstaller | Não |
| `dist` | executável, ZIP e checksum | Não |
| `%LOCALAPPDATA%\br.com.local.financas` | banco, backups e runtime | Não |

## Build e distribuição

`scripts/build_windows.ps1` executa, em ordem:

1. geração do OpenAPI e tipos TypeScript;
2. testes do backend;
3. testes do frontend;
4. typecheck;
5. build da SPA e cópia para o backend;
6. empacotamento PyInstaller;
7. verificação da presença da SPA e migrações;
8. autoteste e smoke test sem Python ou Node no `PATH`;
9. criação do ZIP e checksum SHA-256.

Uma Release deve ser criada a partir de um commit da `main` com CI aprovada e deve anexar o ZIP e o arquivo `.sha256` correspondentes.

## Pontos de extensão

- Novas rotas: `backend/app/api`, mantendo `/api/v1`.
- Novas regras: `backend/app/domain`, com testes de unidade e integração.
- Persistência: modelos e nova revisão Alembic.
- Interface: página/componente no frontend e tipos regenerados.
- Importações futuras: preview, detecção de duplicidade, idempotência e confirmação explícita.

Consulte [modelo de dados](modelo-dados.md), [decisões técnicas](decisoes.md), [migração e recuperação](migracao-recuperacao.md) e [desenvolvimento](desenvolvimento.md).
