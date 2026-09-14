# Controle Financeiro Local

Aplicativo pessoal, manual e local para controle financeiro em português do Brasil e BRL. O frontend React é servido pelo FastAPI na mesma origem; os dados ficam no computador do usuário e o executável Windows não depende de internet, nuvem, banco externo, Python ou Node instalados.

## Usar no Windows

1. Extraia `dist/ControleFinanceiroLocal-windows-x64.zip` para uma pasta gravável.
2. Execute `ControleFinanceiroLocal.exe`.
3. Conclua o onboarding no navegador.
4. Para encerrar o servidor, use **Configurações e dados > Encerrar aplicativo**.

O identificador técnico permanente é `br.com.local.financas`. Os dados ficam em `%LOCALAPPDATA%\br.com.local.financas`; atualizar ou mover o executável não altera esse local. Backups exportados usam a extensão `.finbackup`.

O checksum da entrega está em `dist/ControleFinanceiroLocal-windows-x64.zip.sha256`; valide com `Get-FileHash -Algorithm SHA256` antes de distribuir.

## Desenvolvimento e build

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\setup.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\build_windows.ps1
```

O segundo comando gera OpenAPI/tipos, executa backend, frontend e tipagem, compila a SPA, empacota, roda o autoteste do binário e cria o ZIP somente se tudo passar.

Detalhes: [desenvolvimento](docs/desenvolvimento.md), [arquitetura](docs/arquitetura.md), [modelo de dados](docs/modelo-dados.md), [guia do usuário](docs/guia-usuario.md), [critérios de aceite](docs/criterios-aceite.md), [migração e recuperação](docs/migracao-recuperacao.md) e [registro de testes](docs/registro-testes.md).

Para manutenção e colaboração, consulte [CONTRIBUTING.md](CONTRIBUTING.md) e [SECURITY.md](SECURITY.md).

## Limites deliberados do MVP

Não há integração bancária, importação CSV/OFX, sincronização, múltiplas moedas, múltiplos usuários, rotativo ou pagamento parcial de fatura. SQLite e backups não são criptografados pelo aplicativo; a proteção do disco e da conta Windows continua necessária.
