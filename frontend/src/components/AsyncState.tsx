import type { ReactNode } from "react";

export function AsyncState({ loading, error, empty, children }: { loading: boolean; error: boolean; empty?: boolean; children: ReactNode }) {
  if (loading) return <p className="state" role="status">Carregando dados locais…</p>;
  if (error) return <p className="state error" role="alert">Não foi possível carregar estes dados.</p>;
  if (empty) return <div className="empty"><strong>Sem dados neste período</strong><p>Isso não significa R$ 0,00 confirmado.</p></div>;
  return <>{children}</>;
}

