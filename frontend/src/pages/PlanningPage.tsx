import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { apiFetch, idempotencyHeaders } from "../api/client";
import { Page } from "../components/Page";
import { useAccounts, useCards, useCategories } from "../hooks/useFinanceData";
import { currentMonth, todayIso } from "../lib/forms";
import { formatBrl, parseBrlToMinor } from "../lib/money";

type Occurrence = { id: string; rule_id: string; expected_date: string; expected_amount_minor: number; status: string };
type Rule = { id: string; kind: string; description: string; revision: number };
type PlannedPurchase = { id: string; card_id: string; description: string; expected_date: string; expected_amount_minor: number; status: string; revision: number };
type BudgetItem = { category_id: string; category_name: string; limit_minor: number | null; registered_minor: number; planned_minor: number; projected_minor: number; status: string };

export function PlanningPage() {
  const queryClient = useQueryClient();
  const accounts = useAccounts(); const cards = useCards(); const categories = useCategories();
  const [month, setMonth] = useState(currentMonth());
  const [description, setDescription] = useState(""); const [amount, setAmount] = useState("");
  const [kind, setKind] = useState<"income" | "expense" | "card_purchase">("expense");
  const [target, setTarget] = useState(""); const [day, setDay] = useState(new Date().getDate()); const [categoryId, setCategoryId] = useState("");
  const [budgetValues, setBudgetValues] = useState<Record<string, string>>({});
  const [purchaseDescription, setPurchaseDescription] = useState(""); const [purchaseAmount, setPurchaseAmount] = useState(""); const [purchaseCard, setPurchaseCard] = useState(""); const [purchaseDate, setPurchaseDate] = useState(todayIso());
  const recurrences = useQuery({ queryKey: ["recurrences"], queryFn: () => apiFetch<{ rules: Rule[]; occurrences: Occurrence[] }>("/api/v1/recurrences") });
  const planned = useQuery({ queryKey: ["planned-card-purchases"], queryFn: () => apiFetch<{ items: PlannedPurchase[] }>("/api/v1/planned-card-purchases?status=planned") });
  const budgets = useQuery({ queryKey: ["budgets", month], queryFn: () => apiFetch<{ items: BudgetItem[] }>(`/api/v1/budgets/${month}`) });
  const refresh = () => { void queryClient.invalidateQueries({ queryKey: ["recurrences"] }); void queryClient.invalidateQueries({ queryKey: ["planned-card-purchases"] }); void queryClient.invalidateQueries({ queryKey: ["budgets"] }); void queryClient.invalidateQueries({ queryKey: ["future-balance"] }); };
  const addRecurrence = useMutation({ mutationFn: () => apiFetch("/api/v1/recurrences", { method: "POST", body: JSON.stringify({ kind, description, account_id: kind === "card_purchase" ? null : target, card_id: kind === "card_purchase" ? target : null, day, start_month: month, end_month: null, amount_minor: parseBrlToMinor(amount), category_id: categoryId || null }) }), onSuccess: () => { setDescription(""); setAmount(""); refresh(); } });
  const confirmOccurrence = useMutation({ mutationFn: (item: Occurrence) => apiFetch(`/api/v1/recurrence-occurrences/${item.id}/confirm`, { method: "POST", headers: idempotencyHeaders(), body: JSON.stringify({ actual_date: item.expected_date, actual_amount_minor: item.expected_amount_minor }) }), onSuccess: refresh });
  const confirmPlanned = useMutation({ mutationFn: (item: PlannedPurchase) => apiFetch(`/api/v1/planned-card-purchases/${item.id}/confirm`, { method: "POST" }), onSuccess: refresh });
  const addPlanned = useMutation({ mutationFn: () => apiFetch("/api/v1/planned-card-purchases", { method: "POST", body: JSON.stringify({ card_id: purchaseCard, description: purchaseDescription, category_id: categoryId || null, expected_date: purchaseDate, expected_amount_minor: parseBrlToMinor(purchaseAmount) }) }), onSuccess: () => { setPurchaseDescription(""); setPurchaseAmount(""); refresh(); } });
  const saveBudget = useMutation({ mutationFn: ({ item, value }: { item: BudgetItem; value: string }) => apiFetch(`/api/v1/budgets/${month}/${item.category_id}`, { method: "PUT", body: JSON.stringify({ month, category_id: item.category_id, amount_minor: parseBrlToMinor(value) }) }), onSuccess: refresh });
  const activeTargets = kind === "card_purchase" ? cards.data?.items ?? [] : accounts.data?.items ?? [];
  const pendingOccurrences = recurrences.data?.occurrences.filter(item => item.status === "planned") ?? [];

  return <Page title="Planejamento" description="Organize recorrências, compromissos futuros e limites mensais.">
    <div className="account-grid">
      <section className="panel"><div className="panel-heading"><h2>Nova recorrência</h2></div><div className="form-panel">
        <label className="field"><span>Tipo</span><select value={kind} onChange={e => { setKind(e.target.value as typeof kind); setTarget(""); }}><option value="expense">Despesa</option><option value="income">Receita</option><option value="card_purchase">Compra no cartão</option></select></label>
        <label className="field"><span>Descrição</span><input value={description} onChange={e => setDescription(e.target.value)} /></label>
        <div className="field-row"><label className="field"><span>Valor</span><input inputMode="decimal" value={amount} onChange={e => setAmount(e.target.value)} /></label><label className="field"><span>Dia</span><input type="number" min="1" max="31" value={day} onChange={e => setDay(Number(e.target.value))} /></label></div>
        <label className="field"><span>Destino</span><select value={target} onChange={e => setTarget(e.target.value)}><option value="">Selecione</option>{activeTargets.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Categoria</span><select value={categoryId} onChange={e => setCategoryId(e.target.value)}><option value="">Sem categoria</option>{categories.data?.items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <button className="primary" disabled={!description.trim() || !amount || !target || addRecurrence.isPending} onClick={() => addRecurrence.mutate()}>Salvar recorrência</button>
      </div></section>
      <section className="panel"><div className="panel-heading"><h2>Próximas ocorrências</h2></div>{pendingOccurrences.length ? <div className="timeline">{pendingOccurrences.slice(0, 12).map(item => { const rule = recurrences.data?.rules.find(ruleItem => ruleItem.id === item.rule_id); return <article key={item.id}><time>{item.expected_date}</time><strong>{rule?.description ?? "Recorrência"}</strong><span>{formatBrl(item.expected_amount_minor)}</span><button className="secondary" onClick={() => confirmOccurrence.mutate(item)}>Confirmar</button></article>; })}</div> : <div className="empty">Nenhuma ocorrência pendente.</div>}</section>
      <section className="panel wide"><div className="panel-heading"><h2>Compras planejadas</h2></div><div className="field-row"><label className="field"><span>Descrição</span><input value={purchaseDescription} onChange={e => setPurchaseDescription(e.target.value)} /></label><label className="field"><span>Cartão</span><select value={purchaseCard} onChange={e => setPurchaseCard(e.target.value)}><option value="">Selecione</option>{cards.data?.items.map(card => <option key={card.id} value={card.id}>{card.name}</option>)}</select></label><label className="field"><span>Data prevista</span><input type="date" value={purchaseDate} onChange={e => setPurchaseDate(e.target.value)} /></label><label className="field"><span>Valor estimado</span><input inputMode="decimal" value={purchaseAmount} onChange={e => setPurchaseAmount(e.target.value)} /></label><button className="primary" disabled={!purchaseDescription.trim() || !purchaseCard || !purchaseAmount} onClick={() => addPlanned.mutate()}>Adicionar</button></div>{planned.data?.items.length ? <div className="movement-list">{planned.data.items.map(item => <article className="movement-row" key={item.id}><strong>{item.description}</strong><time>{item.expected_date}</time><span>{formatBrl(item.expected_amount_minor)}</span><button className="secondary" onClick={() => confirmPlanned.mutate(item)}>Confirmar compra</button></article>)}</div> : <div className="empty">Nenhuma compra planejada.</div>}</section>
      <section className="panel wide"><div className="panel-heading"><div><h2>Orçamentos</h2><p>Realizado e previsto usam a mesma base da projeção.</p></div><input type="month" value={month} onChange={e => setMonth(e.target.value)} /></div><div className="budget-grid">{budgets.data?.items.map(item => { const value = budgetValues[item.category_id] ?? (item.limit_minor === null ? "" : (item.limit_minor / 100).toFixed(2).replace(".", ",")); return <article className={`budget-card ${item.status}`} key={item.category_id}><h3>{item.category_name}</h3><strong>{formatBrl(item.projected_minor)}</strong><p>Realizado {formatBrl(item.registered_minor)} · previsto {formatBrl(item.planned_minor)}</p><div className="inline-edit"><input aria-label={`Orçamento de ${item.category_name}`} value={value} placeholder="Sem limite" onChange={e => setBudgetValues({...budgetValues, [item.category_id]: e.target.value})}/><button className="secondary" disabled={!value} onClick={() => saveBudget.mutate({ item, value })}>Salvar</button></div></article>; })}</div></section>
    </div>
  </Page>;
}
