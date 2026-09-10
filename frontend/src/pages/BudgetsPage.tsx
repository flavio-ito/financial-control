import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch } from "../api/client";
import { AsyncState } from "../components/AsyncState";
import { Page } from "../components/Page";
import { currentMonth } from "../lib/forms";
import { formatBrl, parseBrlToMinor } from "../lib/money";

type Item = { id: string; name: string; result: { limit_minor: number | null; registered_minor: number; additional_planned_minor: number; projected_minor: number; percentage: string | null; excess_minor: number; status: string } };

export function BudgetsPage() {
  const [month, setMonth] = useState(currentMonth());
  const [editing, setEditing] = useState<string | null>(null);
  const [value, setValue] = useState("");
  const [asDefault, setAsDefault] = useState(false);
  const queryClient = useQueryClient();
  const budgets = useQuery({ queryKey: ["budgets", month], queryFn: () => apiFetch<{ items: Item[] }>(`/api/v1/budgets/${month}`) });
  const completed = () => { setEditing(null); setValue(""); void queryClient.invalidateQueries({ queryKey: ["budgets", month] }); };
  const save = useMutation({ mutationFn: ({ categoryId, amount }: { categoryId: string; amount: number }) => apiFetch("/api/v1/budgets", { method: "POST", body: JSON.stringify({ category_id: categoryId, month, amount_minor: amount }) }), onSuccess: completed });
  const saveDefault = useMutation({ mutationFn: ({ categoryId, amount }: { categoryId: string; amount: number }) => apiFetch("/api/v1/budget-defaults", { method: "POST", body: JSON.stringify({ category_id: categoryId, effective_from_month: month, amount_minor: amount }) }), onSuccess: completed });

  function submit(categoryId: string) {
    try {
      const amount = parseBrlToMinor(value);
      (asDefault ? saveDefault : save).mutate({ categoryId, amount });
    } catch { /* mantém o campo para correção */ }
  }

  return <Page eyebrow="Global por categoria" title="Orçamentos" description="Registrado e previsto adicional aparecem separados.">
    <label className="month-picker">Mês <input type="month" value={month} onChange={(event) => setMonth(event.target.value)} /></label>
    <AsyncState loading={budgets.isPending} error={budgets.isError} empty={!budgets.data?.items.length}><section className="budget-grid">{budgets.data?.items.map((item) => {
      const result = item.result;
      const percent = result.limit_minor && result.limit_minor > 0 ? Math.min(100, result.registered_minor / result.limit_minor * 100) : 0;
      const status = result.status === "not_configured" ? "Não definido" : result.status === "exceeded" ? "Ultrapassado" : result.status === "risk" ? "Risco de ultrapassar" : result.status === "reached" ? "Limite atingido" : "Dentro do limite";
      return <article className={`budget-card ${result.status}`} key={item.id}><div className="panel-heading"><h2>{item.name}</h2><span>{status}</span></div><strong>{formatBrl(result.registered_minor)}</strong><p>+ {formatBrl(result.additional_planned_minor)} previstos · projetado {formatBrl(result.projected_minor)}</p><div className="progress" role="progressbar" aria-label={`Consumo de ${item.name}`} aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}><span style={{ width: `${percent}%` }} /></div><small>{result.limit_minor === null ? "Sem limite configurado" : `Limite ${formatBrl(result.limit_minor)}${result.percentage ? ` · ${result.percentage}%` : " · sem divisão percentual"}`}</small>{result.excess_minor > 0 && <p className="alert-text">Excesso/risco: {formatBrl(result.excess_minor)}</p>}{editing === item.id ? <div className="budget-edit"><label className="field"><span>Limite em R$</span><input aria-label={`Limite para ${item.name}`} value={value} onChange={(event) => setValue(event.target.value)} placeholder="0,00" /></label><label><input type="checkbox" checked={asDefault} onChange={(event) => setAsDefault(event.target.checked)} /> Padrão a partir de {month}</label><button className="primary" onClick={() => submit(item.id)}>Salvar</button></div> : <button className="text-button" onClick={() => { setEditing(item.id); setAsDefault(false); }}>Definir limite</button>}</article>;
    })}</section></AsyncState>
  </Page>;
}
