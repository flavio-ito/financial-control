import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import { apiFetch } from "../api/client";
import { AsyncState } from "../components/AsyncState";
import { Page } from "../components/Page";
import { useAccounts, useCards, useCategories, useInvestments } from "../hooks/useFinanceData";
import { currentMonth } from "../lib/forms";
import { formatBrl } from "../lib/money";

type OverviewMonth = { month: string; balance_minor: number | null; income_minor: number; expense_minor: number; registered_result_minor: number; categories: Record<string, number>; uncategorized_minor: number };
type OverviewReport = { months: OverviewMonth[] };
type FutureBalanceReport = { current_minor: number; planned_expenses_minor: number; installments_minor: number; future_balance_minor: number };

const monthNames = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"];
const fullMonthNames = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const parseMonth = (month: string, full = false) => {
  const match = /^(\d{4})-(\d{2})$/.exec(month);
  if (!match) return month;
  return full ? `${fullMonthNames[Number(match[2]) - 1]} de ${match[1]}` : `${monthNames[Number(match[2]) - 1]}/${match[1]}`;
};
const compactBrl = (value: number) => new Intl.NumberFormat("pt-BR", { notation: "compact", style: "currency", currency: "BRL" }).format(value / 100);

export function OverviewPage() {
  const initialMonth = currentMonth();
  const [dateFrom, setDateFrom] = useState(initialMonth);
  const [dateTo, setDateTo] = useState(initialMonth);
  const [accountId, setAccountId] = useState("");
  const [cardId, setCardId] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [chartView, setChartView] = useState<"balance" | "cashflow">("balance");
  const accounts = useAccounts();
  const cards = useCards();
  const categories = useCategories();
  const investments = useInvestments();
  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  if (accountId) params.set("account_id", accountId);
  if (cardId) params.set("card_id", cardId);
  if (categoryId) params.set("category_id", categoryId);
  const report = useQuery({ queryKey: ["overview", dateFrom, dateTo, accountId, cardId, categoryId], queryFn: () => apiFetch<OverviewReport>(`/api/v1/reports/overview?${params}`), enabled: Boolean(dateFrom && dateTo && dateFrom <= dateTo) });
  const futureBalance = useQuery({ queryKey: ["future-balance", accountId], queryFn: () => apiFetch<FutureBalanceReport>(`/api/v1/reports/future-balance${accountId ? `?account_id=${encodeURIComponent(accountId)}` : ""}`) });
  const data = useMemo(() => (report.data?.months ?? []).map((item) => ({ ...item, label: parseMonth(item.month), saldo: item.balance_minor, entradas: item.income_minor, saidas: item.expense_minor })), [report.data]);
  const totals = data.reduce((total, item) => ({ income: total.income + item.income_minor, expense: total.expense + item.expense_minor }), { income: 0, expense: 0 });
  const selectedAccounts = accountId ? accounts.data?.items.filter((item) => item.id === accountId) ?? [] : accounts.data?.items ?? [];
  const balance = selectedAccounts.reduce((sum, item) => sum + item.current_balance_minor, 0);
  const investmentTotal = (investments.data?.items.filter((item) => !accountId || item.account_id === accountId) ?? []).reduce((sum, item) => sum + item.amount_minor, 0);
  const categoryData = useMemo(() => {
    const values = new Map<string, number>();
    for (const month of report.data?.months ?? []) {
      for (const [id, value] of Object.entries(month.categories)) values.set(id, (values.get(id) ?? 0) + value);
      if (month.uncategorized_minor) values.set("uncategorized", (values.get("uncategorized") ?? 0) + month.uncategorized_minor);
    }
    return [...values.entries()].map(([id, value]) => ({ name: id === "uncategorized" ? "Sem categoria" : categories.data?.items.find((item) => item.id === id)?.name ?? "Categoria arquivada", value })).sort((a, b) => b.value - a.value).slice(0, 5);
  }, [report.data, categories.data]);
  const categoryTotal = totals.expense || categoryData.reduce((sum, item) => sum + item.value, 0);
  const result = totals.income - totals.expense;
  const loading = accounts.isPending || cards.isPending || categories.isPending || investments.isPending || report.isPending || futureBalance.isPending;
  const error = accounts.isError || cards.isError || categories.isError || investments.isError || report.isError || futureBalance.isError;
  const periodLabel = dateFrom === dateTo ? parseMonth(dateFrom, true) : `${parseMonth(dateFrom, true)} — ${parseMonth(dateTo, true)}`;

  return <Page title="Visão geral" actions={<Link className="primary overview-new-transaction" to="/movimentacoes"><span aria-hidden="true">＋</span> Nova transação</Link>}>
    <section className="overview-filter-card" aria-label="Filtros da visão geral">
      <div className="overview-filter-summary"><span className="overview-period"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg>{periodLabel}</span><button className="overview-filter-toggle" type="button" aria-expanded={filtersOpen} onClick={() => setFiltersOpen((value) => !value)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h10M18 7h2M14 4v6M4 17h2M10 17h10M10 14v6"/></svg>Filtros</button></div>
      {filtersOpen && <div className="overview-filter-fields">
        <fieldset className="period-filter"><legend>Período</legend><label><span>De</span><input type="month" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} /></label><label><span>Até</span><input type="month" value={dateTo} min={dateFrom} onChange={(event) => setDateTo(event.target.value)} /></label></fieldset>
        <label className="field"><span>Conta</span><select value={accountId} onChange={(event) => setAccountId(event.target.value)}><option value="">Todas as contas</option>{accounts.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Cartão</span><select value={cardId} onChange={(event) => setCardId(event.target.value)}><option value="">Todos os cartões</option>{cards.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Categoria</span><select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}><option value="">Todas as categorias</option>{categories.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
      </div>}
    </section>
    {dateFrom > dateTo && <p className="field-error" role="alert">A data inicial deve ser anterior ou igual à data final.</p>}
    <AsyncState loading={loading} error={error}>
      <section className="overview-metrics" aria-label="Resumo do período">
        <article className="metric featured balance"><span>Disponível</span><strong>{formatBrl(balance)}</strong></article><article className="metric investments"><span>Investido</span><strong>{formatBrl(investmentTotal)}</strong></article><article className="metric future-balance"><span>Projeção</span><strong className={(futureBalance.data?.future_balance_minor ?? 0) >= 0 ? "positive" : "negative"}>{formatBrl(futureBalance.data?.future_balance_minor ?? 0)}</strong></article>
        <article className="metric"><span>Entradas</span><strong>{formatBrl(totals.income)}</strong></article><article className="metric"><span>Saídas</span><strong>{formatBrl(totals.expense)}</strong></article><article className="metric"><span>Saldo</span><strong className={result >= 0 ? "positive" : "negative"}>{formatBrl(result)}</strong></article>
      </section>
      <div className="overview-charts">
        <section className="panel chart-panel financial-evolution"><div className="panel-heading"><h2>Evolução financeira</h2></div><div className="chart-tabs" role="tablist" aria-label="Visualização do gráfico"><button type="button" role="tab" aria-selected={chartView === "balance"} className={chartView === "balance" ? "active" : ""} onClick={() => setChartView("balance")}>Saldo</button><button type="button" role="tab" aria-selected={chartView === "cashflow"} className={chartView === "cashflow" ? "active" : ""} onClick={() => setChartView("cashflow")}>Entradas e saídas</button></div><div className="chart-container"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={data} margin={{ top: 18, right: 10, left: -8, bottom: chartView === "cashflow" ? 8 : 0 }} barGap={3} barCategoryGap="24%"><CartesianGrid vertical={false} stroke="var(--color-border)" strokeDasharray="4 5"/><XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--color-text-secondary)" }} dy={8}/><YAxis tickFormatter={compactBrl} tickLine={false} axisLine={false} width={68} tick={{ fontSize: 10, fill: "var(--color-text-secondary)" }}/><Tooltip formatter={(value: number) => formatBrl(value)} contentStyle={{ borderRadius: 8, borderColor: "var(--color-border)", background: "var(--color-surface)", color: "var(--color-text-primary)" }}/>{chartView === "balance" ? <Line name="Saldo" type="linear" dataKey="saldo" stroke="var(--chart-1)" strokeWidth={2.5} dot={{ r: 4, fill: "var(--color-surface)", stroke: "var(--chart-1)", strokeWidth: 2 }} activeDot={{ r: 5 }}/> : <><Bar name="Entradas" dataKey="entradas" fill="var(--chart-1)" radius={[7, 7, 0, 0]} maxBarSize={42}/><Bar name="Saídas" dataKey="saidas" fill="var(--chart-4)" radius={[7, 7, 0, 0]} maxBarSize={42}/><Legend verticalAlign="bottom" iconType="circle" iconSize={9} wrapperStyle={{ fontSize: 11, paddingTop: 10 }}/></>}</ComposedChart></ResponsiveContainer></div></section>
        <section className="panel chart-panel"><div className="panel-heading"><h2>Gastos por categoria</h2></div>{categoryData.length ? <div className="category-bars">{categoryData.map((item, index) => { const percentage = categoryTotal ? item.value / categoryTotal * 100 : 0; return <div className="category-row" key={item.name}><div><span>{item.name}</span><strong>{formatBrl(item.value)}</strong></div><div className="category-track"><span className="category-fill" style={{ width: `${percentage}%`, opacity: 1 - index * .1 }}/><b className="category-percentage" style={{ left: `${percentage}%` }}>{new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(percentage)}%</b></div></div>; })}</div> : <div className="empty">Nenhum gasto encontrado para os filtros selecionados.</div>}</section>
      </div>
      <section className="overview-summary"><span aria-hidden="true">💡</span><div><h2>Resumo financeiro</h2><p>Acompanhe seus principais gastos, orçamento mensal e compromissos futuros em um único lugar.</p></div></section>
    </AsyncState>
  </Page>;
}
