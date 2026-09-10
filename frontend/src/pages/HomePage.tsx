import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import { messages } from "../i18n/ptBR";

type Status = { ready: boolean; app_id: string; data_directory: string };

export function HomePage() {
  const status = useQuery({
    queryKey: ["status"],
    queryFn: () => apiFetch<Status>("/api/v1/status"),
  });

  return (
    <main className="shell">
      <section className="hero" aria-labelledby="page-title">
        <p className="eyebrow">Uso pessoal · BRL · pt-BR</p>
        <h1 id="page-title">{messages.appName}</h1>
        <p className="lead">{messages.localNotice}</p>
        {status.isPending && <p role="status">Carregando dados locais…</p>}
        {status.isError && <p role="alert">Não foi possível carregar o estado da aplicação.</p>}
        {status.data && (
          <div className="ready" role="status">
            <span aria-hidden="true">✓</span>
            <div>
              <strong>Fundação local pronta</strong>
              <p>Banco persistente e sessão protegida ativos.</p>
            </div>
          </div>
        )}
      </section>
      <section className="next" aria-labelledby="next-title">
        <h2 id="next-title">Primeiros passos</h2>
        <p>O assistente de configuração permitirá cadastrar sua primeira conta sem duplicar dados.</p>
        <button type="button" disabled aria-describedby="stage-note">Configurar conta</button>
        <small id="stage-note">Disponível na próxima etapa funcional.</small>
      </section>
    </main>
  );
}

