# Decisões técnicas

## 2026-09-09

- `APP_ID`: `br.com.local.financas`, independente do nome visual futuro.
- Aplicação same-origin vinculada somente a `127.0.0.1`, sem CORS; token bootstrap de uso único fica no fragmento da URL e nunca é persistido.
- Sessão em cookie HttpOnly/SameSite Strict, CSRF e validação de Host/Origin; segredos e tokens não entram em logs ou no SQLite.
- SQLite com `foreign_keys=ON`, `busy_timeout=5000`, sessão por unidade de trabalho e lock local para mutações.
- Alembic é a autoridade exclusiva do schema. Backups antes de migração e restauração atômica fornecem a rota de recuperação.
- Valores monetários são inteiros em centavos BRL, limitados ao intervalo seguro do JavaScript; datas de negócio são civis.
- Previews sensíveis carregam revisão; confirmações obsoletas não aplicam mutação. Idempotência persistente protege reenvios inclusive após reinício.
- Entidades com histórico são arquivadas, não apagadas. Correções e reversões preservam rastreabilidade.
- Distribuição Windows `onedir` foi escolhida para startup e diagnóstico mais previsíveis; o pacote é autocontido.
- Python 3.12 é a versão de referência do desenvolvimento, da integração contínua e do empacotamento Windows.
- Licença do código: MIT. Redistribuição deve preservar avisos das dependências, em especial a exceção de bootloader do PyInstaller.
