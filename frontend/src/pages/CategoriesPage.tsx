import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiFetch } from "../api/client";
import type { Category } from "../api/types";
import { AsyncState } from "../components/AsyncState";
import { Page } from "../components/Page";
import { useAccounts, useCards, useCategories } from "../hooks/useFinanceData";
import { currentMonth } from "../lib/forms";
import { formatBrl } from "../lib/money";

type Values = { name: string };
type OverviewMonth = { month: string; categories: Record<string, number> };
type OverviewReport = { months: OverviewMonth[] };

const monthNames = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const formatMonth = (value: string) => {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  return match ? `${monthNames[Number(match[2]) - 1]} de ${match[1]}` : value;
};
const formatShortMonth = (value: string) => {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  return match ? `${(monthNames[Number(match[2]!) - 1] ?? match[2]!).slice(0, 3).toLowerCase()}/${match[1]}` : value;
};
const compactBrl = (value: number) => new Intl.NumberFormat("pt-BR", { notation: "compact", style: "currency", currency: "BRL" }).format(value / 100);

export function CategoriesPage() {
  const categories = useCategories();
  const accounts = useAccounts();
  const cards = useCards();
  const queryClient = useQueryClient();
  const initialMonth = currentMonth();
  const [dateFrom, setDateFrom] = useState(initialMonth);
  const [dateTo, setDateTo] = useState(initialMonth);
  const [accountFilter, setAccountFilter] = useState("");
  const [cardFilter, setCardFilter] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [expandedCategoryId, setExpandedCategoryId] = useState<string | null>(null);
  const [registering, setRegistering] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [name, setName] = useState("");
  const form = useForm<Values>({ defaultValues: { name: "" } });
  const hasValidPeriod = Boolean(dateFrom && dateTo && dateFrom <= dateTo);
  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  if (accountFilter) params.set("account_id", accountFilter);
  if (cardFilter) params.set("card_id", cardFilter);
  const report = useQuery({
    queryKey: ["overview", dateFrom, dateTo, accountFilter, cardFilter],
    queryFn: () => apiFetch<OverviewReport>(`/api/v1/reports/overview?${params}`),
    enabled: hasValidPeriod,
  });
  const spentByCategory = useMemo(() => {
    const totals = new Map<string, number>();
    for (const month of report.data?.months ?? []) {
      for (const [categoryId, value] of Object.entries(month.categories)) totals.set(categoryId, (totals.get(categoryId) ?? 0) + value);
    }
    return totals;
  }, [report.data]);
  const periodLabel = dateFrom === dateTo ? formatMonth(dateFrom) : `${formatMonth(dateFrom)} — ${formatMonth(dateTo)}`;
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["categories"] });
  const save = useMutation({
    mutationFn: (value: Values) => apiFetch("/api/v1/categories", { method: "POST", body: JSON.stringify(value) }),
    onSuccess: () => { form.reset(); setRegistering(false); refresh(); },
  });
  const rename = useMutation({
    mutationFn: (item: Category) => apiFetch(`/api/v1/categories/${item.id}`, { method: "PUT", body: JSON.stringify({ name, expected_revision: item.revision }) }),
    onSuccess: () => { setEditing(null); refresh(); },
  });
  const archive = useMutation({
    mutationFn: (item: Category) => apiFetch(`/api/v1/categories/${item.id}/archive`, { method: "POST", body: JSON.stringify({ expected_revision: item.revision, reason: "Arquivada pelo usuário" }) }),
    onSuccess: () => { setEditing(null); refresh(); },
  });

  return <Page title="Categorias">
    <section className="panel movement-history categories-history">
      <div className="panel-heading"></div>
      <div className="movement-filter" aria-label="Filtros das categorias">
        <div className="overview-filter-summary"><span className="overview-period"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg>{periodLabel}</span><button className="overview-filter-toggle" type="button" aria-expanded={filtersOpen} onClick={() => setFiltersOpen((value) => !value)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h10M18 7h2M14 4v6M4 17h2M10 17h10M10 14v6"/></svg>Filtros</button></div>
        {filtersOpen && <div className="overview-filter-fields">
          <fieldset className="period-filter"><legend>Período</legend><label><span>De</span><input type="month" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label><label><span>Até</span><input type="month" value={dateTo} min={dateFrom} onChange={(event) => setDateTo(event.target.value)} /></label></fieldset>
          <label className="field"><span>Conta</span><select value={accountFilter} onChange={(event) => setAccountFilter(event.target.value)}><option value="">Todas as contas</option>{accounts.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="field"><span>Cartão</span><select value={cardFilter} onChange={(event) => setCardFilter(event.target.value)}><option value="">Todos os cartões</option>{cards.data?.items.map((item) => { const account = accounts.data?.items.find((candidate) => candidate.id === item.default_account_id); const bank = account?.institution ?? account?.name; return <option key={item.id} value={item.id}>{bank ? `${item.name} (${bank})` : item.name}</option>; })}</select></label>
        </div>}
      </div>
      {!hasValidPeriod && <p className="field-error" role="alert">A data inicial deve ser anterior ou igual à data final.</p>}
      <AsyncState loading={categories.isPending || accounts.isPending || cards.isPending || report.isPending} error={categories.isError || accounts.isError || cards.isError || report.isError} empty={!categories.data?.items.length}>
        <div className="movement-list">
          <div className="movement-list-header" aria-hidden="true"><span>Nome</span><span>Valor gasto</span><span>Ação</span></div>
          {categories.data?.items.map((category) => {
            const expanded = expandedCategoryId === category.id;
            const chartData = (report.data?.months ?? []).map((month) => ({ month: formatShortMonth(month.month), value: month.categories[category.id] ?? 0 }));
            return <Fragment key={category.id}>
              <article className={`movement-row category-summary-row${expanded ? " expanded" : ""}`} role="button" tabIndex={0} aria-expanded={expanded} aria-controls={`category-chart-${category.id}`} onClick={() => setExpandedCategoryId(expanded ? null : category.id)} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setExpandedCategoryId(expanded ? null : category.id); } }}>
                <strong>{category.name}</strong>
                <span>{formatBrl(spentByCategory.get(category.id) ?? 0)}</span>
                <button type="button" className="movement-edit-button" aria-label={`Editar categoria ${category.name}`} title="Editar categoria" onClick={(event) => { event.stopPropagation(); setEditing(category); setName(category.name); }}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button>
              </article>
              {expanded && <section className="category-chart" id={`category-chart-${category.id}`} aria-label={`Evolução financeira de ${category.name}`}>
                <div className="category-chart-heading"><h2>Evolução financeira</h2></div>
                <div className="category-chart-container"><ResponsiveContainer width="100%" height="100%"><LineChart data={chartData} margin={{ top: 18, right: 10, left: -8, bottom: 0 }}><CartesianGrid vertical={false} stroke="var(--color-border)" strokeDasharray="4 5"/><XAxis dataKey="month" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--color-text-secondary)" }} dy={8}/><YAxis tickFormatter={compactBrl} tickLine={false} axisLine={false} width={68} tick={{ fontSize: 10, fill: "var(--color-text-secondary)" }}/><Tooltip formatter={(value: number) => formatBrl(value)} labelStyle={{ color: "var(--color-text-primary)" }} contentStyle={{ borderRadius: 8, borderColor: "var(--color-border)", background: "var(--color-surface)", color: "var(--color-text-primary)" }}/><Line name="Gastos" type="linear" dataKey="value" stroke="var(--chart-1)" strokeWidth={2.5} dot={{ r: 4, fill: "var(--color-surface)", stroke: "var(--chart-1)", strokeWidth: 2 }} activeDot={{ r: 5 }}/></LineChart></ResponsiveContainer></div>
              </section>}
            </Fragment>;
          })}
        </div>
      </AsyncState>
    </section>
    <div className="investment-panel-action"><button className="primary overview-new-transaction" type="button" onClick={() => setRegistering(true)}><span aria-hidden="true">＋</span> Nova categoria</button></div>

    {registering && <div className="modal-backdrop"><form className="modal form-panel transaction-modal" role="dialog" aria-modal="true" aria-labelledby="new-category-title" onSubmit={form.handleSubmit((value) => save.mutate(value))}>
      <h2 id="new-category-title">Nova categoria</h2>
      <label className="field"><span>Nome</span><input required {...form.register("name")} /></label>
      {save.isError && <p className="field-error" role="alert">Não foi possível salvar a categoria.</p>}
      <div className="modal-actions"><button type="button" className="ghost overview-new-transaction" onClick={() => setRegistering(false)}>Cancelar</button><button className="primary overview-new-transaction" disabled={save.isPending}>{save.isPending ? "Salvando…" : "Salvar"}</button></div>
    </form></div>}

    {editing && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="rename-category-title">
      <h2 id="rename-category-title">Renomear categoria</h2>
      <p>O novo nome aparecerá no histórico; snapshots liquidados permanecem preservados.</p>
      <label className="field"><span>Novo nome</span><input value={name} onChange={(event) => setName(event.target.value)} /></label>
      {rename.isError && <p className="field-error" role="alert">Não foi possível renomear a categoria.</p>}
      <div className="modal-actions"><button className="danger" disabled={rename.isPending || archive.isPending} onClick={() => { if (window.confirm(`Arquivar ${editing.name}? Registros históricos manterão o vínculo.`)) archive.mutate(editing); }}>{archive.isPending ? "Arquivando…" : "Arquivar"}</button><button className="ghost" disabled={rename.isPending || archive.isPending} onClick={() => setEditing(null)}>Cancelar</button><button className="primary" disabled={!name.trim() || rename.isPending || archive.isPending} onClick={() => rename.mutate(editing)}>{rename.isPending ? "Salvando…" : "Salvar"}</button></div>
    </section></div>}
  </Page>;
}
