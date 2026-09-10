import { NavLink, Outlet } from "react-router-dom";

const navigation = [
  ["/", "Visão geral"], ["/movimentacoes", "Movimentações"], ["/contas", "Contas"],
  ["/cartoes", "Cartões e faturas"], ["/planejamento", "Planejamento"], ["/orcamentos", "Orçamentos"],
  ["/categorias", "Categorias"], ["/configuracoes", "Configurações e dados"],
] as const;

export function AppShell() {
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="brand"><span>FL</span><strong>Finanças locais</strong></div>
        <nav aria-label="Navegação principal">
          {navigation.map(([to, label]) => <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>)}
        </nav>
        <p className="privacy-note">● Dados somente neste computador</p>
      </aside>
      <div className="content"><Outlet /></div>
    </div>
  );
}

