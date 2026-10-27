import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "../api/client";
import { Page } from "../components/Page";
type InvestmentSettings = { cdi_annual_rate_bps: number; revision: number };

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Não foi possível concluir a operação.";
}

export function SettingsPage() {
  const [message, setMessage] = useState("");
  const [cdiRate, setCdiRate] = useState("14,47");
  const queryClient = useQueryClient();
  const investmentSettings = useQuery({ queryKey: ["investment-settings"], queryFn: () => apiFetch<InvestmentSettings>("/api/v1/settings/investments") });
  useEffect(() => { if (investmentSettings.data) setCdiRate((investmentSettings.data.cdi_annual_rate_bps / 100).toFixed(2).replace(".", ",")); }, [investmentSettings.data]);
  const saveInvestmentSettings = useMutation({
    mutationFn: () => apiFetch<InvestmentSettings>("/api/v1/settings/investments", { method: "PUT", body: JSON.stringify({ cdi_annual_rate_bps: Math.round(Number(cdiRate.replace(",", ".")) * 100), expected_revision: investmentSettings.data?.revision ?? 1 }) }),
    onSuccess: (result) => { queryClient.setQueryData(["investment-settings"], result); setMessage("Taxa anual do CDI atualizada."); },
  });

  return <Page title="Configurações">
    <div className="settings-grid settings-page-grid">
      <section className="panel settings-card">
        <div className="settings-card-heading"><div><h2>Investimentos</h2></div></div>
        <p className="settings-card-description">Defina a taxa anual usada no cálculo diário e composto dos investimentos.</p>
        <div className="settings-inline-form"><label className="field"><span>CDI anual atual</span><div className="money-control"><input inputMode="decimal" value={cdiRate} onChange={(event) => setCdiRate(event.target.value)} /><span>%</span></div></label><button className="primary" disabled={saveInvestmentSettings.isPending || !/^\d{1,3}([,.]\d{1,2})?$/.test(cdiRate)} onClick={() => saveInvestmentSettings.mutate()}>{saveInvestmentSettings.isPending ? "Salvando…" : "Salvar taxa"}</button></div>
        {message && <p className="success" role="status">{message}</p>}{saveInvestmentSettings.isError && <p className="error" role="alert">{errorMessage(saveInvestmentSettings.error)}</p>}
      </section>
    </div>
  </Page>;
}
