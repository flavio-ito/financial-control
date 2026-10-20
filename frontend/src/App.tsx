import { useEffect, useState } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { initializeSession } from "./api/client";
import { apiFetch } from "./api/client";
import { AppShell } from "./components/AppShell";
import { messages } from "./i18n/ptBR";
import { AccountsPage } from "./pages/AccountsPage";
import { CategoriesPage } from "./pages/CategoriesPage";
import { MovementsPage } from "./pages/MovementsPage";
import { InvestmentsPage } from "./pages/InvestmentsPage";
import { OverviewPage } from "./pages/OverviewPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SetupPage } from "./pages/SetupPage";

function AuthenticatedApp() {
  const setup = useQuery({ queryKey: ["setup"], queryFn: () => apiFetch<{ has_account: boolean; setup_step: number }>("/api/v1/setup") });
  if (setup.isPending) return <main className="center" role="status">Carregando configuração local…</main>;
  if (setup.isError) return <main className="center error" role="alert">Não foi possível ler a configuração local.</main>;
  if (!setup.data.has_account || setup.data.setup_step < 6) return <SetupPage initialStep={setup.data.has_account ? Math.max(2, Math.min(5, setup.data.setup_step)) : setup.data.setup_step} />;
  return <Routes><Route element={<AppShell />}><Route index element={<OverviewPage />} /><Route path="movimentacoes" element={<MovementsPage />} /><Route path="contas" element={<AccountsPage />} /><Route path="cartoes" element={<AccountsPage />} /><Route path="investimentos" element={<InvestmentsPage />} /><Route path="categorias" element={<CategoriesPage />} /><Route path="configuracoes" element={<SettingsPage />} /><Route path="*" element={<OverviewPage />} /></Route></Routes>;
}

export function App() {
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");

  useEffect(() => {
    void initializeSession().then(() => setState("ready"), () => setState("error"));
  }, []);

  if (state === "loading") return <main className="center" role="status">{messages.loading}</main>;
  if (state === "error") return <main className="center error" role="alert">{messages.sessionError}</main>;

  return (
    <BrowserRouter>
      <AuthenticatedApp />
    </BrowserRouter>
  );
}
