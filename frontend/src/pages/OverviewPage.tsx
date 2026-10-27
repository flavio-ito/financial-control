import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Link } from "react-router-dom";
import { apiFetch } from "../api/client";
import { AsyncState } from "../components/AsyncState";
import { Page } from "../components/Page";
import { useAccounts, useCategories, useInvestments } from "../hooks/useFinanceData";
import { currentMonth } from "../lib/forms";
import { formatBrl } from "../lib/money";

type OverviewMonth = { month: string; balance_minor: number | null; income_minor: number; expense_minor: number; registered_result_minor: number; categories: Record<string, number>; uncategorized_minor: number };
type OverviewReport = { months: OverviewMonth[] };
type FutureBalanceReport = { current_minor: number; planned_income_minor: number; planned_expenses_minor: number; installments_minor: number; future_balance_minor: number; date_to: string };

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
  const dateFrom = initialMonth;
  const dateTo = initialMonth;
  const initialYear = Number(initialMonth.slice(0, 4));
  const initialMonthIndex = Number(initialMonth.slice(5, 7)) - 1;
  const evolutionStart = new Date(initialYear, initialMonthIndex - 3, 1);
  const evolutionFrom = `${evolutionStart.getFullYear()}-${String(evolutionStart.getMonth() + 1).padStart(2, "0")}`;
  const projectionEnd = new Date(initialYear, initialMonthIndex + 4, 0);
  const projectionDate = `${projectionEnd.getFullYear()}-${String(projectionEnd.getMonth() + 1).padStart(2, "0")}-${String(projectionEnd.getDate()).padStart(2, "0")}`;
  const accounts = useAccounts();
  const categories = useCategories();
  const investments = useInvestments();
  const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo });
  const evolutionParams = new URLSearchParams({ date_from: evolutionFrom, date_to: initialMonth });
  const report = useQuery({ queryKey: ["overview", dateFrom, dateTo], queryFn: () => apiFetch<OverviewReport>(`/api/v1/reports/overview?${params}`) });
  const evolutionReport = useQuery({ queryKey: ["overview-evolution", evolutionFrom, initialMonth], queryFn: () => apiFetch<OverviewReport>(`/api/v1/reports/overview?${evolutionParams}`) });
  const futureBalance = useQuery({ queryKey: ["future-balance", projectionDate], queryFn: () => apiFetch<FutureBalanceReport>(`/api/v1/reports/future-balance?date_to=${projectionDate}`) });
  const data = useMemo(() => (report.data?.months ?? []).map((item) => ({ ...item, label: parseMonth(item.month), saldo: item.balance_minor, entradas: item.income_minor, saidas: item.expense_minor })), [report.data]);
  const totals = data.reduce((total, item) => ({ income: total.income + item.income_minor, expense: total.expense + item.expense_minor }), { income: 0, expense: 0 });
  const balance = (accounts.data?.items ?? []).reduce((sum, item) => sum + item.current_balance_minor, 0);
  const evolutionData = useMemo(() => {
    const historicalMonths = evolutionReport.data?.months ?? [];
    const completedMonths = historicalMonths.filter((item) => item.month !== initialMonth).slice(-3);
    const historical = historicalMonths.map((item) => ({
      label: parseMonth(item.month),
      saldoReal: item.month === initialMonth ? balance : item.balance_minor,
      saldoProjetado: item.month === initialMonth ? balance : null,
    }));
    const forecast = Array.from({ length: 3 }, (_, index) => {
      const date = new Date(initialYear, initialMonthIndex + index + 1, 1);
      const month = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
      const projectedEnd = futureBalance.data?.future_balance_minor ?? balance;
      return { label: parseMonth(month), saldoReal: null, saldoProjetado: Math.round(balance + (projectedEnd - balance) * ((index + 1) / 3)) };
    });
    return { points: [...historical, ...forecast] };
  }, [balance, evolutionReport.data, futureBalance.data, initialMonth, initialMonthIndex, initialYear]);
  const investmentTotal = (investments.data?.items ?? []).reduce((sum, item) => sum + item.amount_minor, 0);
  const categoryData = useMemo(() => {
    const values = new Map<string, number>();
    for (const month of report.data?.months ?? []) {
      for (const [id, value] of Object.entries(month.categories)) values.set(id, (values.get(id) ?? 0) + value);
      if (month.uncategorized_minor) values.set("uncategorized", (values.get("uncategorized") ?? 0) + month.uncategorized_minor);
    }
    const sorted = [...values.entries()].map(([id, value]) => ({ name: id === "uncategorized" ? "Sem categoria" : categories.data?.items.find((item) => item.id === id)?.name ?? "Categoria arquivada", value })).sort((a, b) => b.value - a.value);
    if (sorted.length <= 5) return sorted;
    return [...sorted.slice(0, 5), { name: "Demais categorias", value: sorted.slice(5).reduce((sum, item) => sum + item.value, 0) }];
  }, [report.data, categories.data]);
  const categoryTotal = totals.expense || categoryData.reduce((sum, item) => sum + item.value, 0);
  const result = totals.income - totals.expense;
  const loading = accounts.isPending || categories.isPending || investments.isPending || report.isPending || evolutionReport.isPending || futureBalance.isPending;
  const error = accounts.isError || categories.isError || investments.isError || report.isError || evolutionReport.isError || futureBalance.isError;
  const periodLabel = dateFrom === dateTo ? parseMonth(dateFrom, true) : `${parseMonth(dateFrom, true)} — ${parseMonth(dateTo, true)}`;
  const leadingCategory = categoryData[0];
  const leadingCategoryPercentage = leadingCategory && categoryTotal ? leadingCategory.value / categoryTotal * 100 : 0;
  const resultInsight = result < 0
    ? `As saídas superaram as entradas em ${formatBrl(Math.abs(result))} no período.`
    : result > 0
      ? `As entradas superaram as saídas em ${formatBrl(result)} no período.`
      : "Entradas e saídas ficaram equilibradas no período.";

  return <Page title="Visão geral" actions={<Link className="primary overview-new-transaction" to="/movimentacoes"><span aria-hidden="true">＋</span> Nova transação</Link>}>
    {dateFrom > dateTo && <p className="field-error" role="alert">A data inicial deve ser anterior ou igual à data final.</p>}
    <AsyncState loading={loading} error={error}>
      <section className="overview-metric-section" aria-labelledby="current-position-title"><div className="overview-section-heading"><div></div></div><div className="overview-metrics overview-position-metrics"><article className="metric balance"><span>Disponível</span><strong>{formatBrl(balance)}</strong><small>Saldo atual das contas</small></article><article className="metric investments"><span>Investido</span><strong>{formatBrl(investmentTotal)}</strong><small>Total aplicado</small></article><article className="metric future-balance"><span>Projeção</span><strong className={(futureBalance.data?.future_balance_minor ?? 0) >= 0 ? "positive" : "negative"}>{formatBrl(futureBalance.data?.future_balance_minor ?? 0)}</strong><small>Após compromissos futuros</small></article></div></section>
      <section className="overview-metric-section overview-result-section" aria-labelledby="period-result-title">
        <div className="overview-section-heading"><div><h2 id="period-result-title">Resumo do mês</h2></div></div>
        <div className="overview-metrics overview-period-metrics"><article className="metric"><span>Entradas</span><strong>{formatBrl(totals.income)}</strong><small>Recebimentos registrados</small></article><article className="metric"><span>Saídas</span><strong>{formatBrl(totals.expense)}</strong><small>Despesas registradas</small></article><article className="metric"><span>Saldo</span><strong className={result >= 0 ? "positive" : "negative"}>{formatBrl(result)}</strong></article></div>
        <div className="overview-result-footer"><Link className="overview-details-link" to="/movimentacoes">Ver detalhes</Link></div>
      </section>
      <div className="overview-charts">
        <section className="panel chart-panel financial-evolution"><div className="panel-heading"><div><h2>Evolução financeira</h2></div><div className="evolution-legend" aria-label="Legenda do gráfico"><span><i/>Real</span><span><i className="projected"/>Previsão</span></div></div>{evolutionData.points.length ? <><div className="chart-container" role="img" aria-label="Gráfico de linha do saldo dos três meses anteriores e da previsão para os três meses futuros"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={evolutionData.points} margin={{ top: 18, right: 10, left: -8, bottom: 0 }}><CartesianGrid vertical={false} stroke="var(--color-border)" strokeDasharray="4 5"/><XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--color-text-secondary)" }} dy={8}/><YAxis tickFormatter={compactBrl} tickLine={false} axisLine={false} width={68} tick={{ fontSize: 10, fill: "var(--color-text-secondary)" }}/><Tooltip formatter={(value: number, name: string) => [formatBrl(value), name]} contentStyle={{ borderRadius: 8, borderColor: "var(--color-border)", background: "var(--color-surface)", color: "var(--color-text-primary)" }}/><Line name="Saldo real" type="monotone" dataKey="saldoReal" connectNulls={false} stroke="var(--chart-1)" strokeWidth={2.5} dot={false} activeDot={false}/><Line name="Saldo previsto" type="monotone" dataKey="saldoProjetado" connectNulls={false} stroke="var(--color-text-tertiary)" strokeWidth={2.5} strokeDasharray="6 5" dot={false} activeDot={false}/></ComposedChart></ResponsiveContainer></div></> : <div className="empty">Ainda não há histórico suficiente para exibir a evolução do saldo.</div>}</section>
        <section className="panel chart-panel category-panel"><div className="panel-heading"><div><h2>Gastos por categoria</h2></div></div>{categoryData.length ? <div className="category-bars">{categoryData.map((item, index) => { const percentage = categoryTotal ? item.value / categoryTotal * 100 : 0; return <div className="category-row" key={item.name}><div><span>{index + 1}. {item.name}</span><strong>{formatBrl(item.value)}</strong><b>{new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(percentage)}%</b></div><div className="category-track" role="img" aria-label={`${item.name}: ${formatBrl(item.value)}, ${new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(percentage)}% dos gastos`}><span className="category-fill" style={{ width: `${Math.min(percentage, 100)}%`, opacity: 1 - index * .08 }}/></div></div>; })}</div> : <div className="empty">Nenhum gasto encontrado para os filtros selecionados.</div>}</section>
      </div>
    </AsyncState>
  </Page>;
}
