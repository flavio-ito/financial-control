# Contribuindo

Este é um projeto individual, mas toda alteração deve deixar um histórico curto, verificável e reversível. A branch `main` representa código funcional; funcionalidades, correções e manutenção devem ser desenvolvidas em branches temporárias e integradas por pull request.

## Ambiente necessário

- Windows 10 ou 11.
- Python 3.12.
- Node.js 22 e npm 10.
- Git.

Prepare o ambiente a partir da raiz do repositório:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\setup.ps1
```

O script cria ou reutiliza `.venv`, instala as dependências fixadas em `backend/requirements.lock` e executa `npm ci` no frontend. Se `.venv` tiver sido criado com outra versão do Python, remova apenas esse ambiente descartável, recrie-o com Python 3.12 e execute o setup novamente.

## Executar em desenvolvimento

Compile o frontend antes da primeira execução:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build_frontend.ps1
$env:PYTHONPATH = "$PWD\backend"
.\.venv\Scripts\python.exe -m app.launcher
```

Para evitar abrir o navegador ou para isolar dados de desenvolvimento:

```powershell
$env:FINANCAS_NO_BROWSER = "1"
$env:FINANCAS_DATA_DIR = "$PWD\build\dev-data"
```

Nunca teste manualmente usando um banco real. O diretório padrão de dados do usuário é `%LOCALAPPDATA%\br.com.local.financas`.

## Fluxo de alteração

1. Atualize a base: `git switch main` e `git pull --ff-only`.
2. Crie uma branch curta, por exemplo `feature/exportacao-csv`, `fix/calculo-fatura`, `chore/dependencias` ou `docs/arquitetura`.
3. Faça uma alteração de propósito único.
4. Adicione ou atualize testes quando houver mudança de comportamento.
5. Atualize a documentação e `docs/changelog.md` quando necessário.
6. Execute as verificações locais.
7. Envie a branch e abra um pull request para `main`.
8. Faça merge somente com a CI aprovada; prefira squash merge.

Commits devem explicar o resultado no imperativo, por exemplo `Corrige fechamento de conexão no backup`. Não misture atualização ampla de dependências, refatoração e funcionalidade financeira no mesmo pull request.

## Verificações obrigatórias

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests -q
npm.cmd --prefix frontend test -- --run
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

Quando o contrato da API mudar, regenere os tipos:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\generate_api_types.ps1
git diff -- frontend/src/api/schema.d.ts
```

O arquivo gerado deve acompanhar a alteração do backend no mesmo pull request.

Para mudanças em inicialização, persistência, migração, backup, dependências ou empacotamento, execute também:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

Esse comando só produz o ZIP depois de executar testes, tipagem, build, PyInstaller e o smoke test do pacote.

## Regras para mudanças financeiras

- Valores monetários atravessam a API como inteiros em centavos; não use `float`.
- Datas financeiras são datas civis (`YYYY-MM-DD`); instantes de auditoria são UTC.
- Operações com múltiplos efeitos devem permanecer atômicas.
- Não apague histórico financeiro; use estados, cancelamento, anulação, reversão ou estorno.
- Respeite `revision`, previews e idempotência nas mutações aplicáveis.
- Alterações de schema devem ser feitas exclusivamente por uma nova migração Alembic.
- Uma migração nunca deve depender de editar uma migração já publicada.
- Mudanças que afetem banco ou backup exigem teste de compatibilidade e recuperação.

## Checklist do pull request

- [ ] O escopo está limitado a um problema.
- [ ] Não há banco, backup, log, token ou dado pessoal no commit.
- [ ] Testes relevantes foram adicionados ou atualizados.
- [ ] Backend, frontend, tipagem e build passam.
- [ ] Migração Alembic foi criada, se o schema mudou.
- [ ] OpenAPI e tipos foram regenerados, se a API mudou.
- [ ] Documentação e changelog foram atualizados.
- [ ] Backup, restauração e pacote foram testados quando impactados.

Consulte também [arquitetura](docs/arquitetura.md), [modelo de dados](docs/modelo-dados.md), [desenvolvimento](docs/desenvolvimento.md) e [critérios de aceite](docs/criterios-aceite.md).
