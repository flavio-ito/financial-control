import type { ReactNode } from "react";
import { useMutation } from "@tanstack/react-query";
import { NavLink, Outlet } from "react-router-dom";
import { apiFetch } from "../api/client";

type NavigationItem = { to: string; label: string; icon: ReactNode };
const iconProps = { viewBox: "0 0 24 24", "aria-hidden": true } as const;

const navigation: NavigationItem[] = [
  { to: "/", label: "Visão geral", icon: <svg {...iconProps}><rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" /><rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" /></svg> },
  { to: "/movimentacoes", label: "Transações", icon: <svg {...iconProps}><path d="M4 7h15M7 4 4 7l3 3M20 17H5m12-3 3 3-3 3" /></svg> },
  { to: "/investimentos", label: "Investimentos", icon: <svg {...iconProps}><path d="M4 19V14m4 5v-7m4 7v-4m4 4V9m4 10V5M4 11l5-4 4 3 7-7" /></svg> },
  { to: "/cartoes", label: "Contas e cartões", icon: <svg {...iconProps}><rect x="4" y="5" width="16" height="14" rx="2" /><path d="M4 9h16m-12 5h5" /></svg> },
];

const secondaryNavigation: NavigationItem[] = [
  { to: "/categorias", label: "Categorias", icon: <svg {...iconProps}><path d="M13 5H6a2 2 0 0 0-2 2v4l8 8 7-7-7-7Z" /><circle cx="8" cy="9" r="1" /><path d="m15 6 5 5a2 2 0 0 1 0 3l-4 4" /></svg> },
  { to: "/configuracoes", label: "Configurações", icon: <svg {...iconProps}><circle cx="12" cy="12" r="3" /><path d="M19 14.5a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06a1.7 1.7 0 0 0-1.88-.34A1.7 1.7 0 0 0 13.6 20.4v.1h-3.2v-.1a1.7 1.7 0 0 0-1.03-1.53 1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 5 14.5a1.7 1.7 0 0 0-1.5-1H3.4v-3h.1A1.7 1.7 0 0 0 5 9.47a1.7 1.7 0 0 0-.34-1.88L4.6 7.53 7.43 4.7l.06.06a1.7 1.7 0 0 0 1.88.34A1.7 1.7 0 0 0 10.4 3.6v-.1h3.2v.1a1.7 1.7 0 0 0 1.03 1.5 1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19 9.47a1.7 1.7 0 0 0 1.5 1.03h.1v3h-.1a1.7 1.7 0 0 0-1.5 1Z" /></svg> },
];

function NavigationLinks({ items }: { items: NavigationItem[] }) {
  return items.map(({ to, label, icon }) => <NavLink key={to} to={to} end={to === "/"}>{icon}<span>{label}</span></NavLink>);
}

export function AppShell() {
  const shutdown = useMutation({ mutationFn: () => apiFetch("/api/v1/application/shutdown", { method: "POST" }) });

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true"><img src="/minhas_financas_logo.png" alt="" /></span>
          <span className="brand-copy"><strong>Minhas Finanças</strong></span>
        </div>
        <nav aria-label="Navegação principal">
          <div className="sidebar-links"><NavigationLinks items={navigation} /></div>
          <div className="sidebar-links sidebar-links-secondary"><NavigationLinks items={secondaryNavigation} /></div>
        </nav>
        <button
          className="sidebar-exit"
          type="button"
          disabled={shutdown.isPending || shutdown.isSuccess}
          onClick={() => shutdown.mutate()}
        >
          <svg {...iconProps}><path d="M10 5H5v14h5M14 8l4 4-4 4m4-4H9" /></svg>
          <span>{shutdown.isSuccess ? "Encerrando…" : "Sair"}</span>
        </button>
      </aside>
      <div className="content"><Outlet /></div>
    </div>
  );
}
