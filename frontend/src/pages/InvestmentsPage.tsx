import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { z } from "zod";
import { apiFetch, idempotencyHeaders } from "../api/client";
import type { CashEntry, Investment, Page as PageType } from "../api/types";
import { AsyncState } from "../components/AsyncState";
import { MoneyField } from "../components/MoneyField";
import { Page } from "../components/Page";
import { useAccounts, useInvestments } from "../hooks/useFinanceData";
import { formatDateBr } from "../lib/dates";
import { currentMonth, moneyText, requiredText, todayIso } from "../lib/forms";
import { formatBrl, parseBrlToMinor } from "../lib/money";

const investmentSchema = z.object({
  accountId: requiredText,
  amount: moneyText,
  cdi: z.string().trim().refine((value) => /^\d{1,4}([,.]\d{1,2})?$/.test(value) && Number(value.replace(",", ".")) <= 1000, "Informe um percentual entre 0 e 1.000."),
});
const withdrawalSchema = z.object({ investmentId: requiredText, amount: moneyText });
type InvestmentHistoryPage = PageType<CashEntry> & {
  summary: { income_minor: number; withdrawal_minor: number; net_minor: number };
  series: Array<{ date: string; portfolio_minor: number }>;
};
type PeriodMode = "month" | "year";
type InvestmentMovementType = "contribution" | "withdrawal";
const investmentMonthNames = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const investmentMonthShortNames = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
const formatInvestmentMonth = (value: string) => {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  return match ? `${investmentMonthNames[Number(match[2]) - 1]} de ${match[1]}` : value;
};
const chartAxisBrl = (value: number) => new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 }).format(value / 100);
const formatCdi = (value: number) => `${(value / 100).toLocaleString("pt-BR", { maximumFractionDigits: 2 })}% do CDI`;

export function InvestmentsPage() {
  const initialMonth = currentMonth();
  const accounts = useAccounts();
  const investments = useInvestments();
  const queryClient = useQueryClient();
  const [pageNumber, setPageNumber] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [dateFrom, setDateFrom] = useState(initialMonth);
  const [dateTo, setDateTo] = useState(initialMonth);
  const [periodMode, setPeriodMode] = useState<PeriodMode>("month");
  const [periodPickerOpen, setPeriodPickerOpen] = useState(false);
  const [pickerYear, setPickerYear] = useState(Number(initialMonth.slice(0, 4)));
  const periodPickerRef = useRef<HTMLDivElement>(null);
  const [registering, setRegistering] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
  const [investmentMovementType, setInvestmentMovementType] = useState<InvestmentMovementType>("contribution");
  const [editing, setEditing] = useState<Investment | null>(null);
  const [editingEntry, setEditingEntry] = useState<CashEntry | null>(null);
  const [entryDescription, setEntryDescription] = useState("");
  const [entryAmount, setEntryAmount] = useState("");
  const [entryReason, setEntryReason] = useState("");
  const historyParams = new URLSearchParams({ page: String(pageNumber), page_size: String(pageSize) });
  if (dateFrom) historyParams.set("date_from", `${dateFrom}-01`);
  if (dateTo) {
    const lastDay = new Date(Number(dateTo.slice(0, 4)), Number(dateTo.slice(5, 7)), 0).getDate();
    historyParams.set("date_to", `${dateTo}-${String(lastDay).padStart(2, "0")}`);
  }
  const hasValidPeriod = !dateFrom || !dateTo || dateFrom <= dateTo;
  const entries = useQuery({ queryKey: ["investment-yields", pageNumber, pageSize, dateFrom, dateTo], queryFn: () => apiFetch<InvestmentHistoryPage>(`/api/v1/investment-yields?${historyParams}`), enabled: hasValidPeriod, refetchInterval: 60_000 });
  const form = useForm<z.input<typeof investmentSchema>>({ resolver: zodResolver(investmentSchema), defaultValues: { accountId: "", amount: "", cdi: "100" } });
  const editForm = useForm<z.input<typeof investmentSchema>>({ resolver: zodResolver(investmentSchema), defaultValues: { accountId: "", amount: "", cdi: "100" } });
  const withdrawalForm = useForm<z.input<typeof withdrawalSchema>>({ resolver: zodResolver(withdrawalSchema), defaultValues: { investmentId: "", amount: "" } });
  const refresh = () => { void queryClient.invalidateQueries({ queryKey: ["investments"] }); };
  const add = useMutation({
    mutationFn: (value: z.output<typeof investmentSchema>) => apiFetch("/api/v1/investments", { method: "POST", body: JSON.stringify({ account_id: value.accountId, amount_minor: value.amount, cdi_percentage: Math.round(Number(value.cdi.replace(",", ".")) * 100) }) }),
    onSuccess: () => { form.reset({ accountId: "", amount: "", cdi: "100" }); setRegistering(false); refresh(); },
  });
  const edit = useMutation({
    mutationFn: ({ item, value }: { item: Investment; value: z.output<typeof investmentSchema> }) => apiFetch(`/api/v1/investments/${item.id}`, { method: "PUT", body: JSON.stringify({ account_id: value.accountId, amount_minor: value.amount, cdi_percentage: Math.round(Number(value.cdi.replace(",", ".")) * 100), expected_revision: item.revision }) }),
    onSuccess: () => { setEditing(null); refresh(); },
  });
  const editEntry = useMutation({
    mutationFn: (entry: CashEntry) => apiFetch(`/api/v1/cash-entries/${entry.id}`, { method: "PUT", body: JSON.stringify({ account_id: entry.account_id, category_id: entry.category_id, kind: entry.kind, description: entryDescription, amount_minor: parseBrlToMinor(entryAmount), planned_date: entry.planned_date, effective_date: entry.effective_date, status: entry.status, note: null, expected_revision: entry.revision, reason: entryReason }) }),
    onSuccess: () => { setEditingEntry(null); void queryClient.invalidateQueries({ queryKey: ["cash-entries"] }); },
  });
  const moveInvestment = useMutation({
    mutationFn: (value: z.output<typeof withdrawalSchema>) => apiFetch(investmentMovementType === "contribution" ? "/api/v1/investment-contributions" : "/api/v1/investment-withdrawals", { method: "POST", headers: idempotencyHeaders(), body: JSON.stringify(investmentMovementType === "contribution" ? { investment_id: value.investmentId, amount_minor: value.amount, contribution_date: todayIso() } : { investment_id: value.investmentId, amount_minor: value.amount, withdrawal_date: todayIso() }) }),
    onSuccess: () => { withdrawalForm.reset(); setWithdrawing(false); void queryClient.invalidateQueries({ queryKey: ["investment-yields"] }); void queryClient.invalidateQueries({ queryKey: ["investments"] }); void queryClient.invalidateQueries({ queryKey: ["accounts"] }); void queryClient.invalidateQueries({ queryKey: ["cash-entries"] }); },
  });
  const accountName = (id: string) => { const account = accounts.data?.items.find((item) => item.id === id); return account ? (account.institution || account.name) : "Banco não encontrado"; };
  const periodLabel = dateFrom === dateTo ? formatInvestmentMonth(dateFrom) : `${formatInvestmentMonth(dateFrom)} — ${formatInvestmentMonth(dateTo)}`;
  const selectedYear = dateFrom.slice(0, 4);
  const periodPickerLabel = periodMode === "year" ? selectedYear : periodLabel;
  const selectPeriodMode = (mode: PeriodMode) => {
    setPeriodMode(mode);
    setPageNumber(1);
    if (mode === "month") {
      const month = pickerYear === Number(initialMonth.slice(0, 4)) ? initialMonth.slice(5, 7) : "01";
      setDateFrom(`${pickerYear}-${month}`);
      setDateTo(`${pickerYear}-${month}`);
    } else {
      setDateFrom(`${pickerYear}-01`);
      setDateTo(`${pickerYear}-12`);
    }
  };
  const selectMonth = (month: string) => { if (/^\d{4}-\d{2}$/.test(month)) { setDateFrom(month); setDateTo(month); setPageNumber(1); setPeriodPickerOpen(false); } };
  const selectYear = (year: string) => {
    if (!/^\d{4}$/.test(year)) return;
    setPickerYear(Number(year));
    setDateFrom(`${year}-01`);
    setDateTo(`${year}-12`);
    setPageNumber(1);
    setPeriodPickerOpen(false);
  };
  const visibleYears = Array.from({ length: 12 }, (_, index) => pickerYear - 5 + index);
  useEffect(() => {
    if (!periodPickerOpen) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!periodPickerRef.current?.contains(event.target as Node)) setPeriodPickerOpen(false);
    };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setPeriodPickerOpen(false); };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("pointerdown", closeOnOutsideClick); document.removeEventListener("keydown", closeOnEscape); };
  }, [periodPickerOpen]);
  const pageSubtotal = entries.data?.items.reduce((sum, entry) => sum + entry.signed_amount_minor, 0) ?? 0;
  const portfolioTotal = investments.data?.items.reduce((sum, item) => sum + item.amount_minor, 0) ?? 0;
  const sortedInvestments = [...(investments.data?.items ?? [])].sort((a, b) => b.amount_minor - a.amount_minor);
  const chartData = (entries.data?.series ?? []).map((day) => ({ date: day.date, label: formatDateBr(day.date), portfolio: day.portfolio_minor }));
  const portfolioValues = chartData.map((day) => day.portfolio);
  const portfolioMin = portfolioValues.length ? Math.min(...portfolioValues) : 0;
  const portfolioMax = portfolioValues.length ? Math.max(...portfolioValues) : 0;
  const portfolioRange = portfolioMax - portfolioMin;
  const portfolioPadding = Math.max(portfolioRange * 0.2, portfolioMax * 0.005, 100);
  const portfolioDomain: [number, number] = [Math.max(0, Math.floor(portfolioMin - portfolioPadding)), Math.ceil(portfolioMax + portfolioPadding)];
  const portfolioTickInterval = (portfolioDomain[1] - portfolioDomain[0]) / 4;
  const portfolioTicks = Array.from({ length: 5 }, (_, index) => portfolioDomain[0] + portfolioTickInterval * index);
  const totalPages = Math.max(1, Math.ceil((entries.data?.total ?? 0) / pageSize));
  const paginationItems: Array<number | "ellipsis"> = [];
  const visiblePageNumbers = totalPages <= 7
    ? Array.from({ length: totalPages }, (_, index) => index + 1)
    : Array.from(new Set([1, pageNumber - 1, pageNumber, pageNumber + 1, totalPages])).filter((page) => page >= 1 && page <= totalPages).sort((a, b) => a - b);
  visiblePageNumbers.forEach((page, index) => {
    if (index > 0 && page - visiblePageNumbers[index - 1]! > 1) paginationItems.push("ellipsis");
    paginationItems.push(page);
  });

  return <Page title="Investimentos" description="Acompanhe sua carteira, os rendimentos e as movimentações em um só lugar." actions={<button className="primary overview-new-transaction investment-page-action" type="button" onClick={() => setRegistering(true)}><span aria-hidden="true">＋</span> Novo investimento</button>}>
    <div className="account-grid">
      <section className="panel wide investments-panel"><div className="panel-heading investment-portfolio-heading"><div><h2>Seus investimentos</h2><p>{sortedInvestments.length} {sortedInvestments.length === 1 ? "investimento ativo" : "investimentos ativos"}</p></div><div className="investment-portfolio-total"><span>Total investido</span><strong>{formatBrl(portfolioTotal)}</strong></div></div><AsyncState loading={investments.isPending || accounts.isPending} error={investments.isError || accounts.isError} empty={!sortedInvestments.length}><div className="account-cards investment-cards">{sortedInvestments.map((item) => { const share = portfolioTotal > 0 ? item.amount_minor / portfolioTotal * 100 : 0; return <article key={item.id}><div className="investment-card-heading"><h3>{accountName(item.account_id)}</h3><button type="button" className="movement-edit-button" aria-label={`Editar investimento de ${accountName(item.account_id)}`} title="Editar investimento" onClick={() => { setEditing(item); editForm.reset({ accountId: item.account_id, amount: (item.amount_minor / 100).toFixed(2).replace(".", ","), cdi: (item.cdi_percentage / 100).toFixed(2).replace(".", ",") }); }}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button></div><strong>{formatBrl(item.amount_minor)}</strong><div className="investment-card-meta"><span>{formatCdi(item.cdi_percentage)}</span><span>{share.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% da carteira</span></div><div className="investment-share-track" aria-label={`${share.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}% da carteira`}><span style={{ width: `${Math.max(2, share)}%` }} /></div></article>; })}</div></AsyncState></section>
      <section className="panel wide movement-history investment-history">
        <div className="panel-heading investment-history-heading">
          <div><h2>Desempenho e rendimentos</h2><p className="investment-section-description">Visão consolidada do período selecionado</p></div>
          <div className="investment-history-toolbar">
            <div className="investment-date-filter" ref={periodPickerRef}>
              <span className="investment-date-filter-label">Período</span>
              <button className="investment-date-trigger" type="button" aria-haspopup="dialog" aria-expanded={periodPickerOpen} onClick={() => setPeriodPickerOpen((open) => !open)}>
                <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg>
                <span>{periodPickerLabel}</span>
                <svg className="investment-date-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg>
              </button>
              {periodPickerOpen && <div className="investment-date-popover" role="dialog" aria-label="Selecionar período">
                <div className="investment-date-popover-value"><span>{periodPickerLabel}</span><button type="button" aria-label="Fechar seletor de período" onClick={() => setPeriodPickerOpen(false)}>×</button></div>
                <div className="investment-period-toggle" role="group" aria-label="Visualizar por mês ou ano">
                  <button type="button" className={periodMode === "month" ? "active" : ""} aria-pressed={periodMode === "month"} onClick={() => selectPeriodMode("month")}>Mês</button>
                  <button type="button" className={periodMode === "year" ? "active" : ""} aria-pressed={periodMode === "year"} onClick={() => selectPeriodMode("year")}>Ano</button>
                </div>
                <div className="investment-period-shortcuts" aria-label="Atalhos de período"><button type="button" onClick={() => selectMonth(initialMonth)}>Mês atual</button><button type="button" onClick={() => { const date = new Date(Number(initialMonth.slice(0, 4)), Number(initialMonth.slice(5, 7)) - 2, 1); selectMonth(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`); }}>Mês anterior</button><button type="button" onClick={() => selectYear(initialMonth.slice(0, 4))}>Ano atual</button></div>
                {periodMode === "month" ? <>
                  <div className="investment-date-navigation"><button type="button" aria-label="Ano anterior" onClick={() => setPickerYear((year) => year - 1)}>‹</button><strong>{pickerYear}</strong><button type="button" aria-label="Próximo ano" onClick={() => setPickerYear((year) => year + 1)}>›</button></div>
                  <div className="investment-month-grid">{investmentMonthShortNames.map((month, index) => { const value = `${pickerYear}-${String(index + 1).padStart(2, "0")}`; return <button type="button" key={month} className={dateFrom === value && dateTo === value ? "selected" : ""} aria-pressed={dateFrom === value && dateTo === value} onClick={() => selectMonth(value)}>{month}</button>; })}</div>
                </> : <>
                  <div className="investment-date-navigation"><button type="button" aria-label="Anos anteriores" onClick={() => setPickerYear((year) => year - 12)}>‹</button><strong>{visibleYears[0]}–{visibleYears[visibleYears.length - 1]}</strong><button type="button" aria-label="Próximos anos" onClick={() => setPickerYear((year) => year + 12)}>›</button></div>
                  <div className="investment-year-grid">{visibleYears.map((year) => <button type="button" key={year} className={selectedYear === String(year) ? "selected" : ""} aria-pressed={selectedYear === String(year)} onClick={() => selectYear(String(year))}>{year}</button>)}</div>
                </>}
              </div>}
            </div>
            <button className="primary overview-new-transaction investment-withdraw-button" type="button" onClick={() => { setInvestmentMovementType("contribution"); setWithdrawing(true); }}><span aria-hidden="true">＋</span> Movimentar investimento</button>
          </div>
        </div>
        {!hasValidPeriod && <p className="field-error" role="alert">A data inicial deve ser anterior ou igual à data final.</p>}
        <AsyncState loading={entries.isPending || accounts.isPending} error={entries.isError || accounts.isError}>
          <div className="investment-period-summary" aria-label={`Resumo de ${periodLabel}`}>
            <div className="income"><span><i aria-hidden="true">↗</i> Rendimentos</span><strong className="positive">+ {formatBrl(entries.data?.summary.income_minor ?? 0)}</strong></div>
            <div className="withdrawal"><span><i aria-hidden="true">↘</i> Saques</span><strong className="negative">− {formatBrl(entries.data?.summary.withdrawal_minor ?? 0)}</strong></div>
            <div className="net"><span><i aria-hidden="true">=</i> Resultado líquido</span><strong className={(entries.data?.summary.net_minor ?? 0) < 0 ? "negative" : "positive"}>{(entries.data?.summary.net_minor ?? 0) >= 0 ? "+ " : ""}{formatBrl(entries.data?.summary.net_minor ?? 0)}</strong></div>
          </div>
          {chartData.length > 0 && <section className="investment-chart" aria-labelledby="investment-chart-title"><div className="investment-chart-heading"><div><h3 id="investment-chart-title">Evolução do patrimônio</h3></div><div className="investment-chart-legend" aria-hidden="true"></div></div><div className="investment-chart-container"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={chartData} margin={{ top: 14, right: 10, left: 0, bottom: 4 }}><CartesianGrid vertical={false} stroke="var(--color-border)" strokeDasharray="4 5"/><XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--color-text-secondary)" }} dy={8}/><YAxis domain={portfolioDomain} ticks={portfolioTicks} tickFormatter={chartAxisBrl} tickLine={false} axisLine={false} width={82} tick={{ fontSize: 10, fill: "var(--color-text-secondary)" }}/><Tooltip formatter={(value: number) => [formatBrl(value), "Patrimônio total"]} contentStyle={{ borderRadius: 8, borderColor: "var(--color-border)", background: "var(--color-surface)", color: "var(--color-text-primary)" }}/><Line name="Patrimônio total" type="linear" dataKey="portfolio" stroke="var(--chart-1)" strokeWidth={2.5} dot={false} activeDot={false}/></ComposedChart></ResponsiveContainer></div></section>}
          {entries.data?.total === 0
            ? <div className="empty"><strong>Sem dados neste período</strong><p>Os totais acima consideram todo o período selecionado.</p></div>
            : <>
                <div className="investment-table-heading"><div><h3>Lançamentos no período</h3></div><span>{entries.data?.total ?? 0} registros</span></div><div className="movement-list investment-movement-list">
                  <div className="movement-list-header" aria-hidden="true"><span>Banco e descrição</span><span>Data</span><span>Valor</span></div>
                  {entries.data?.items.map((entry) => { const account = accounts.data?.items.find((item) => item.id === entry.account_id); return <article className="movement-row" key={entry.id}><div className="investment-entry-primary"><strong title={account?.name}>{account?.institution ?? account?.name ?? "—"}</strong><small>{entry.description}</small></div><time dateTime={entry.effective_date ?? entry.planned_date}>{formatDateBr(entry.effective_date ?? entry.planned_date)}</time><span className={entry.signed_amount_minor < 0 ? "negative" : "positive"}>{entry.signed_amount_minor > 0 ? "+ " : ""}{formatBrl(entry.signed_amount_minor)}</span><button type="button" className="movement-edit-button" aria-label={`Editar ${entry.description}`} title="Editar registro" onClick={() => { setEditingEntry(entry); setEntryDescription(entry.description); setEntryAmount((Math.abs(entry.signed_amount_minor) / 100).toFixed(2).replace(".", ",")); setEntryReason(""); }}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button></article>; })}
                  <div className="movement-total"><strong>Subtotal desta página</strong><strong className={pageSubtotal < 0 ? "negative" : "positive"}>{formatBrl(pageSubtotal)}</strong></div>
                </div>
                <nav className="pagination investment-pagination" aria-label="Paginação do histórico">
                  <div className="investment-pagination-summary"><span>Página {pageNumber} de {totalPages}</span><label><span className="sr-only">Itens por página</span><select aria-label="Itens por página" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPageNumber(1); }}>{[10, 15, 20, 25, 50].map((size) => <option key={size} value={size}>{size} / página</option>)}</select></label></div>
                  <div className="investment-pagination-navigation">
                    <button className="pagination-direction previous" type="button" disabled={pageNumber === 1} onClick={() => setPageNumber((value) => value - 1)}><span aria-hidden="true">‹</span> Anterior</button>
                    <div className="investment-pagination-pages">{paginationItems.map((item, index) => item === "ellipsis" ? <span className="pagination-ellipsis" key={`ellipsis-${index}`}>…</span> : <button type="button" key={item} className={item === pageNumber ? "active" : ""} aria-current={item === pageNumber ? "page" : undefined} aria-label={`Ir para a página ${item}`} onClick={() => setPageNumber(item)}>{item}</button>)}</div>
                    <button className="pagination-direction next" type="button" disabled={pageNumber === totalPages} onClick={() => setPageNumber((value) => value + 1)}>Próxima <span aria-hidden="true">›</span></button>
                  </div>
                </nav>
              </>}
        </AsyncState>
      </section>
    </div>
    {registering && <div className="modal-backdrop"><form className="modal form-panel investment-modal transaction-modal" role="dialog" aria-modal="true" aria-labelledby="new-investment-title" onSubmit={form.handleSubmit((value) => add.mutate(investmentSchema.parse(value)))}><h2 id="new-investment-title">Novo investimento</h2><label className="field"><span>Banco associado</span><select {...form.register("accountId")}><option value="">Selecione</option>{accounts.data?.items.map((account) => <option key={account.id} value={account.id}>{account.institution || account.name}</option>)}</select>{form.formState.errors.accountId && <small className="field-error">Selecione um banco.</small>}</label><MoneyField label="Valor investido" registration={form.register("amount")} error={form.formState.errors.amount} /><label className="field"><span>Percentual do CDI</span><div className="money-control"><input inputMode="decimal" placeholder="100" {...form.register("cdi")} /><span>%</span></div>{form.formState.errors.cdi && <small className="field-error">{form.formState.errors.cdi.message}</small>}</label>{add.isError && <p className="field-error" role="alert">Não foi possível salvar o investimento.</p>}<div className="modal-actions"><button type="button" className="ghost overview-new-transaction" onClick={() => setRegistering(false)}>Cancelar</button><button className="primary overview-new-transaction" disabled={add.isPending || !accounts.data?.items.length}>{add.isPending ? "Salvando…" : "Registrar"}</button></div></form></div>}
    {withdrawing && <div className="modal-backdrop"><form className="modal form-panel investment-modal transaction-modal" role="dialog" aria-modal="true" aria-labelledby="investment-movement-title" onSubmit={withdrawalForm.handleSubmit((value) => moveInvestment.mutate(withdrawalSchema.parse(value)))}><h2 id="investment-movement-title">Movimentar investimento</h2><div className="investment-movement-toggle" role="group" aria-label="Tipo de movimentação"><button type="button" className={investmentMovementType === "contribution" ? "active" : ""} aria-pressed={investmentMovementType === "contribution"} onClick={() => setInvestmentMovementType("contribution")}>Novo aporte</button><button type="button" className={investmentMovementType === "withdrawal" ? "active" : ""} aria-pressed={investmentMovementType === "withdrawal"} onClick={() => setInvestmentMovementType("withdrawal")}>Saque</button></div><p className="investment-movement-description">{investmentMovementType === "contribution" ? "Adicione um novo valor a um investimento existente." : "Retire um valor do saldo disponível no investimento."}</p><label className="field"><span>Investimento</span><select {...withdrawalForm.register("investmentId")}><option value="">Selecione</option>{investments.data?.items.map((item) => <option key={item.id} value={item.id}>{accountName(item.account_id)} · {formatBrl(item.amount_minor)}</option>)}</select>{withdrawalForm.formState.errors.investmentId && <small className="field-error">Selecione um investimento.</small>}</label><MoneyField label={investmentMovementType === "contribution" ? "Valor do aporte" : "Valor do saque"} registration={withdrawalForm.register("amount")} error={withdrawalForm.formState.errors.amount} />{moveInvestment.isError && <p className="field-error" role="alert">{investmentMovementType === "contribution" ? "Não foi possível registrar o aporte." : "Não foi possível registrar o saque. Confira o saldo disponível."}</p>}<div className="modal-actions"><button type="button" className="ghost overview-new-transaction" onClick={() => setWithdrawing(false)}>Cancelar</button><button className="primary overview-new-transaction" disabled={moveInvestment.isPending}>{moveInvestment.isPending ? "Registrando…" : investmentMovementType === "contribution" ? "Confirmar aporte" : "Confirmar saque"}</button></div></form></div>}
    {editing && <div className="modal-backdrop"><form className="modal form-panel investment-modal transaction-modal" role="dialog" aria-modal="true" aria-labelledby="edit-investment-title" onSubmit={editForm.handleSubmit((value) => edit.mutate({ item: editing, value: investmentSchema.parse(value) }))}><h2 id="edit-investment-title">Editar investimento</h2><label className="field"><span>Banco associado</span><select disabled {...editForm.register("accountId")}><option value="">Selecione</option>{accounts.data?.items.map((account) => <option key={account.id} value={account.id}>{account.institution || account.name}</option>)}</select>{editForm.formState.errors.accountId && <small className="field-error">Selecione um banco.</small>}</label><MoneyField label="Valor investido (use aporte ou saque para alterar)" registration={editForm.register("amount")} error={editForm.formState.errors.amount} disabled /><label className="field"><span>Percentual do CDI</span><div className="money-control"><input inputMode="decimal" {...editForm.register("cdi")} /><span>%</span></div>{editForm.formState.errors.cdi && <small className="field-error">{editForm.formState.errors.cdi.message}</small>}</label>{edit.isError && <p className="field-error" role="alert">Não foi possível editar o investimento.</p>}<div className="modal-actions"><button type="button" className="ghost overview-new-transaction" onClick={() => setEditing(null)}>Cancelar</button><button className="primary overview-new-transaction" disabled={edit.isPending}>{edit.isPending ? "Salvando…" : "Salvar"}</button></div></form></div>}
    {editingEntry && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true"><h2>Editar movimentação</h2><p>A alteração guarda antes/depois na auditoria.</p><label className="field"><span>Descrição</span><input value={entryDescription} onChange={(event) => setEntryDescription(event.target.value)} /></label><label className="field"><span>Valor positivo</span><input inputMode="decimal" value={entryAmount} onChange={(event) => setEntryAmount(event.target.value)} /></label><label className="field"><span>Justificativa</span><textarea value={entryReason} onChange={(event) => setEntryReason(event.target.value)} /></label>{editEntry.isError && <p className="field-error">Confira o valor e a justificativa.</p>}<div className="modal-actions"><button className="ghost" onClick={() => setEditingEntry(null)}>Cancelar</button><button className="primary" disabled={!entryReason.trim() || editEntry.isPending} onClick={() => editEntry.mutate(editingEntry)}>{editEntry.isPending ? "Salvando…" : "Salvar alteração"}</button></div></section></div>}
  </Page>;
}
