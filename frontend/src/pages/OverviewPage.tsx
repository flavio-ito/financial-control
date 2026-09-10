import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { apiFetch } from "../api/client";
import { AsyncState } from "../components/AsyncState";
import { Page } from "../components/Page";
import { useAccounts, useCards, useInvoices } from "../hooks/useFinanceData";
import { formatDateBr, formatMonthBr } from "../lib/dates";
import { currentMonth } from "../lib/forms";
import { formatBrl } from "../lib/money";

type Monthly = { summary: { income_minor: number; expense_minor: number; registered_result_minor: number; cash_flow_minor: number; uncategorized_minor: number }; coverage: string; comparison: { reliable: boolean } | null };
type Budget = { id: string; name: string; result: { limit_minor: number | null; registered_minor: number; additional_planned_minor: number; projected_minor: number; excess_minor: number; status: string } };
type Projection = { projected_minor: number; incomplete_by_account: boolean };

export function OverviewPage() {
  const [month, setMonth] = useState(currentMonth());
  const accounts = useAccounts();
  const cards = useCards();
  const invoices = useInvoices();
  const report = useQuery({ queryKey: ["monthly", month], queryFn: () => apiFetch<Monthly>(`/api/v1/reports/monthly/${month}`) });
  const budgets = useQuery({ queryKey: ["budgets", month], queryFn: () => apiFetch<{ items: Budget[] }>(`/api/v1/budgets/${month}`) });
  const projection = useQuery({ queryKey: ["projection-overview", month], queryFn: () => apiFetch<Projection>(`/api/v1/reports/projection?through_month=${month}`) });
  const total = accounts.data?.items.reduce((sum, account) => sum + account.current_balance_minor, 0) ?? 0;
  const risky = budgets.data?.items.filter((item) => ["exceeded", "risk"].includes(item.result.status)) ?? [];
  return <Page eyebrow={`Competência ${formatMonthBr(month)}`} title="Visão geral" description="Caixa, consumo e compromissos permanecem separados.">
    <label className="field month-picker"><span>Mês analisado</span><input type="month" value={month} onChange={(event) => setMonth(event.target.value)} /></label>
    <AsyncState loading={accounts.isPending || report.isPending} error={accounts.isError || report.isError}>
      <section className="metrics" aria-label="Resumo mensal"><article className="metric featured"><span>Saldo atual</span><strong>{formatBrl(total)}</strong><small>{accounts.data?.items.length ?? 0} conta(s) incluída(s)</small></article><article className="metric"><span>Receitas efetivadas</span><strong>{formatBrl(report.data?.summary.income_minor ?? 0)}</strong><small>Caixa confirmado</small></article><article className="metric"><span>Despesas registradas</span><strong>{formatBrl(report.data?.summary.expense_minor ?? 0)}</strong><small>Inclui parcelas pela fatura</small></article><article className="metric"><span>Resultado registrado</span><strong>{formatBrl(report.data?.summary.registered_result_minor ?? 0)}</strong><small>Não equivale à variação bancária</small></article><article className="metric"><span>Fluxo de caixa efetivado</span><strong>{formatBrl(report.data?.summary.cash_flow_minor ?? 0)}</strong><small>Inclui transferências/pagamentos por conta; consolidado reconciliado</small></article><article className="metric"><span>Sem categoria</span><strong>{formatBrl(report.data?.summary.uncategorized_minor ?? 0)}</strong><small><Link to="/movimentacoes">Abrir lançamentos</Link></small></article></section>
      <div className="grid-two"><section className="panel"><div className="panel-heading"><h2>Contas</h2><span className="quality">Cobertura: {report.data?.coverage === "complete" ? "completa declarada" : report.data?.coverage === "partial" ? "parcial — comparação inconclusiva" : "desconhecida"}</span></div>{accounts.data?.items.length ? <table><thead><tr><th>Conta</th><th>Saldo</th></tr></thead><tbody>{accounts.data.items.map((account) => <tr key={account.id}><td>{account.name}</td><td>{formatBrl(account.current_balance_minor)}</td></tr>)}</tbody></table> : <div className="empty">Nenhuma conta ativa.</div>}</section><section className="panel"><div className="panel-heading"><h2>Cartões</h2><span>Limite estimado, não saldo</span></div>{cards.data?.items.length ? cards.data.items.map((card) => <div className="card-line" key={card.id}><div><strong>{card.name}</strong><small>{formatBrl(card.commitment_minor)} comprometidos</small></div><span>{formatBrl(card.available_estimated_minor)}</span></div>) : <div className="empty">Nenhum cartão. Isso não é gasto zero.</div>}<Link className="text-button" to="/cartoes">Ver origem em faturas</Link></section></div>
      <div className="grid-two"><section className="panel"><div className="panel-heading"><h2>Faturas próximas</h2><span>Compromissos futuros</span></div>{invoices.data?.items.filter((item) => item.state !== "settled").slice(0, 5).map((invoice) => <div className="card-line" key={invoice.id}><div><strong>{formatMonthBr(invoice.reference_month)}</strong><small>Vence {formatDateBr(invoice.due_date)} · {invoice.state}</small></div><span>{formatBrl(invoice.payable_minor)}</span></div>)}{!invoices.data?.items.some((item) => item.state !== "settled") && <div className="empty">Sem faturas futuras registradas; não equivale a compromisso zero confirmado.</div>}</section><section className="panel"><div className="panel-heading"><h2>Orçamento e risco</h2><span>Global por categoria</span></div>{risky.length ? risky.map((item) => <div className={`card-line alert-${item.result.status}`} key={item.id}><div><strong>{item.name}</strong><small>{item.result.status === "exceeded" ? "Limite ultrapassado" : "Risco de ultrapassar"}</small></div><span>{formatBrl(item.result.excess_minor)}</span></div>) : <div className="empty">Nenhum alerta com os dados disponíveis.</div>}<Link className="text-button" to="/orcamentos">Abrir detalhes</Link></section></div>
      <section className="panel"><div className="panel-heading"><h2>Projeção de caixa</h2><span>{projection.data?.incomplete_by_account ? "Incompleta por conta" : "Contas atribuídas"}</span></div><strong className="projection-total">{formatBrl(projection.data?.projected_minor ?? total)}</strong><p>Saldo projetado até o mês selecionado; compras no cartão entram uma vez pelo pagamento da fatura.</p><Link className="text-button" to="/planejamento">Ver linha do tempo e premissas</Link></section>
    </AsyncState>
  </Page>;
}
