import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
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
const investmentMonthNames = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const formatInvestmentMonth = (value: string) => {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  return match ? `${investmentMonthNames[Number(match[2]) - 1]} de ${match[1]}` : value;
};

export function InvestmentsPage() {
  const initialMonth = currentMonth();
  const accounts = useAccounts();
  const investments = useInvestments();
  const queryClient = useQueryClient();
  const [pageNumber, setPageNumber] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [dateFrom, setDateFrom] = useState(initialMonth);
  const [dateTo, setDateTo] = useState(initialMonth);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [managingEntries, setManagingEntries] = useState(false);
  const [withdrawing, setWithdrawing] = useState(false);
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
  const entries = useQuery({ queryKey: ["investment-yields", pageNumber, pageSize, dateFrom, dateTo], queryFn: () => apiFetch<PageType<CashEntry>>(`/api/v1/investment-yields?${historyParams}`), enabled: hasValidPeriod, refetchInterval: 60_000 });
  const manualEntries = useQuery({ queryKey: ["cash-entries", "investments", "manual"], queryFn: () => apiFetch<PageType<CashEntry>>("/api/v1/cash-entries?investment_only=true&source=manual&active_only=true&page_size=200") });
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
  const withdraw = useMutation({
    mutationFn: (value: z.output<typeof withdrawalSchema>) => apiFetch("/api/v1/investment-withdrawals", { method: "POST", headers: idempotencyHeaders(), body: JSON.stringify({ investment_id: value.investmentId, amount_minor: value.amount, withdrawal_date: todayIso() }) }),
    onSuccess: () => { withdrawalForm.reset(); setWithdrawing(false); void queryClient.invalidateQueries({ queryKey: ["investment-yields"] }); void queryClient.invalidateQueries({ queryKey: ["investments"] }); void queryClient.invalidateQueries({ queryKey: ["accounts"] }); void queryClient.invalidateQueries({ queryKey: ["cash-entries"] }); },
  });
  const accountName = (id: string) => { const account = accounts.data?.items.find((item) => item.id === id); return account ? (account.institution || account.name) : "Banco não encontrado"; };
  const periodLabel = dateFrom === dateTo ? formatInvestmentMonth(dateFrom) : `${formatInvestmentMonth(dateFrom)} — ${formatInvestmentMonth(dateTo)}`;

  return <Page title="Investimentos">
    <div className="account-grid">
      <section className="panel wide investments-panel"><div className="panel-heading"></div><AsyncState loading={investments.isPending || accounts.isPending} error={investments.isError || accounts.isError} empty={!investments.data?.items.length}><div className="account-cards investment-cards">{investments.data?.items.map((item) => <article key={item.id}><strong>{formatBrl(item.amount_minor)}</strong><h3>{accountName(item.account_id)}</h3><button type="button" className="movement-edit-button" aria-label={`Editar investimento de ${accountName(item.account_id)}`} title="Editar investimento" onClick={() => { setEditing(item); editForm.reset({ accountId: item.account_id, amount: (item.amount_minor / 100).toFixed(2).replace(".", ","), cdi: (item.cdi_percentage / 100).toFixed(2).replace(".", ",") }); }}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button></article>)}</div></AsyncState><div className="investment-panel-action"><button className="primary overview-new-transaction" type="button" onClick={() => setRegistering(true)}><span aria-hidden="true">＋</span> Novo investimento</button></div></section>
      <section className="panel wide movement-history investment-history"><div className="panel-heading"><h2>Histórico de rendimentos</h2></div><div className="movement-filter" aria-label="Filtros do histórico de rendimentos"><div className="overview-filter-summary"><span className="overview-period"><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg>{periodLabel}</span><button className="overview-filter-toggle" type="button" aria-expanded={filtersOpen} onClick={() => setFiltersOpen((value) => !value)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h10M18 7h2M14 4v6M4 17h2M10 17h10M10 14v6"/></svg>Filtros</button></div>{filtersOpen && <div className="overview-filter-fields"><fieldset className="period-filter"><legend>Período</legend><label><span>De</span><input type="month" value={dateFrom} onChange={(event) => { setDateFrom(event.target.value); setPageNumber(1); }} /></label><label><span>Até</span><input type="month" value={dateTo} min={dateFrom} onChange={(event) => { setDateTo(event.target.value); setPageNumber(1); }} /></label></fieldset></div>}</div>{!hasValidPeriod && <p className="field-error" role="alert">A data inicial deve ser anterior ou igual à data final.</p>}<AsyncState loading={entries.isPending || accounts.isPending} error={entries.isError || accounts.isError} empty={entries.data?.total === 0}><div className="movement-list"><div className="movement-list-header" aria-hidden="true"><span>Tipo</span><span>Banco</span><span>Data</span><span>Valor</span><span>Ação</span></div>{entries.data?.items.map((entry) => { const account = accounts.data?.items.find((item) => item.id === entry.account_id); const canEdit = entry.source === "manual"; return <article className="movement-row" key={entry.id}><strong>{entry.kind === "income" ? "Entrada" : "Saída"}</strong><span title={account?.name}>{account?.institution ?? account?.name ?? "—"}</span><time dateTime={entry.effective_date ?? entry.planned_date}>{formatDateBr(entry.effective_date ?? entry.planned_date)}</time><span className={entry.signed_amount_minor < 0 ? "negative" : "positive"}>{formatBrl(entry.signed_amount_minor)}</span><button type="button" className="movement-edit-button" disabled={!canEdit} aria-label={`Editar ${entry.description}`} title={canEdit ? "Editar registro" : "Este registro não pode ser editado manualmente"} onClick={() => { setEditingEntry(entry); setEntryDescription(entry.description); setEntryAmount((Math.abs(entry.signed_amount_minor) / 100).toFixed(2).replace(".", ",")); setEntryReason(""); }}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button></article>; })}<div className="movement-total"><strong>Total</strong><strong className={(entries.data?.items.reduce((sum, entry) => sum + entry.signed_amount_minor, 0) ?? 0) < 0 ? "negative" : "positive"}>{formatBrl(entries.data?.items.reduce((sum, entry) => sum + entry.signed_amount_minor, 0) ?? 0)}</strong></div></div><div className="pagination"><label>Itens por página <select value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPageNumber(1); }}>{[10, 15, 20, 25, 50].map((size) => <option key={size} value={size}>{size}</option>)}</select></label><button disabled={pageNumber === 1} onClick={() => setPageNumber((value) => value - 1)}>Anterior</button><span>Página {pageNumber}</span><button disabled={!entries.data || pageNumber * entries.data.page_size >= entries.data.total} onClick={() => setPageNumber((value) => value + 1)}>Próxima</button></div></AsyncState></section>
      <div className="investment-panel-action investment-history-actions"><button className="secondary investment-new-button" onClick={() => setManagingEntries(true)}>Editar Registros</button><button className="primary overview-new-transaction" type="button" onClick={() => setWithdrawing(true)}><span aria-hidden="true">＋</span> Registrar saque</button></div>
    </div>
    {registering && <div className="modal-backdrop"><form className="modal form-panel investment-modal transaction-modal" role="dialog" aria-modal="true" aria-labelledby="new-investment-title" onSubmit={form.handleSubmit((value) => add.mutate(investmentSchema.parse(value)))}><h2 id="new-investment-title">Novo investimento</h2><label className="field"><span>Banco associado</span><select {...form.register("accountId")}><option value="">Selecione</option>{accounts.data?.items.map((account) => <option key={account.id} value={account.id}>{account.institution || account.name}</option>)}</select>{form.formState.errors.accountId && <small className="field-error">Selecione um banco.</small>}</label><MoneyField label="Valor investido" registration={form.register("amount")} error={form.formState.errors.amount} /><label className="field"><span>Percentual do CDI</span><div className="money-control"><input inputMode="decimal" placeholder="100" {...form.register("cdi")} /><span>%</span></div>{form.formState.errors.cdi && <small className="field-error">{form.formState.errors.cdi.message}</small>}</label>{add.isError && <p className="field-error" role="alert">Não foi possível salvar o investimento.</p>}<div className="modal-actions"><button type="button" className="ghost overview-new-transaction" onClick={() => setRegistering(false)}>Cancelar</button><button className="primary overview-new-transaction" disabled={add.isPending || !accounts.data?.items.length}>{add.isPending ? "Salvando…" : "Registrar"}</button></div></form></div>}
    {withdrawing && <div className="modal-backdrop"><form className="modal form-panel investment-modal transaction-modal" role="dialog" aria-modal="true" aria-labelledby="withdraw-investment-title" onSubmit={withdrawalForm.handleSubmit((value) => withdraw.mutate(withdrawalSchema.parse(value)))}><h2 id="withdraw-investment-title">Registrar saque</h2><label className="field"><span>Investimento</span><select {...withdrawalForm.register("investmentId")}><option value="">Selecione</option>{investments.data?.items.map((item) => <option key={item.id} value={item.id}>{accountName(item.account_id)} · {formatBrl(item.amount_minor)}</option>)}</select>{withdrawalForm.formState.errors.investmentId && <small className="field-error">Selecione um investimento.</small>}</label><MoneyField label="Valor do saque" registration={withdrawalForm.register("amount")} error={withdrawalForm.formState.errors.amount} />{withdraw.isError && <p className="field-error" role="alert">Não foi possível registrar o saque. Confira o saldo disponível.</p>}<div className="modal-actions"><button type="button" className="ghost overview-new-transaction" onClick={() => setWithdrawing(false)}>Cancelar</button><button className="primary overview-new-transaction" disabled={withdraw.isPending}>{withdraw.isPending ? "Registrando…" : "Confirmar saque"}</button></div></form></div>}
    {editing && <div className="modal-backdrop"><form className="modal form-panel" role="dialog" aria-modal="true" onSubmit={editForm.handleSubmit((value) => edit.mutate({ item: editing, value: investmentSchema.parse(value) }))}><h2>Editar investimento</h2><label className="field"><span>Banco associado</span><select {...editForm.register("accountId")}><option value="">Selecione</option>{accounts.data?.items.map((account) => <option key={account.id} value={account.id}>{account.institution || account.name}</option>)}</select>{editForm.formState.errors.accountId && <small className="field-error">Selecione um banco.</small>}</label><MoneyField label="Valor investido" registration={editForm.register("amount")} error={editForm.formState.errors.amount} /><label className="field"><span>Percentual do CDI</span><div className="money-control"><input inputMode="decimal" {...editForm.register("cdi")} /><span>%</span></div>{editForm.formState.errors.cdi && <small className="field-error">{editForm.formState.errors.cdi.message}</small>}</label>{edit.isError && <p className="field-error" role="alert">Não foi possível editar o investimento.</p>}<div className="modal-actions"><button type="button" className="ghost" onClick={() => setEditing(null)}>Cancelar</button><button className="primary" disabled={edit.isPending}>{edit.isPending ? "Salvando…" : "Salvar"}</button></div></form></div>}
    {managingEntries && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="edit-investment-records-title"><h2 id="edit-investment-records-title">Editar registros</h2><div className="list">{manualEntries.data?.items.map((entry) => <article className="list-row" key={entry.id}><div><strong>{entry.description}</strong><small>{formatDateBr(entry.effective_date ?? entry.planned_date)} · {formatBrl(entry.signed_amount_minor)}</small></div><button className="text-button" onClick={() => { setManagingEntries(false); setEditingEntry(entry); setEntryDescription(entry.description); setEntryAmount((Math.abs(entry.signed_amount_minor) / 100).toFixed(2).replace(".", ",")); setEntryReason(""); }}>Editar</button></article>)}</div><div className="modal-actions"><button className="ghost" onClick={() => setManagingEntries(false)}>Fechar</button></div></section></div>}
    {editingEntry && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true"><h2>Editar movimentação</h2><p>A alteração guarda antes/depois na auditoria.</p><label className="field"><span>Descrição</span><input value={entryDescription} onChange={(event) => setEntryDescription(event.target.value)} /></label><label className="field"><span>Valor positivo</span><input inputMode="decimal" value={entryAmount} onChange={(event) => setEntryAmount(event.target.value)} /></label><label className="field"><span>Justificativa</span><textarea value={entryReason} onChange={(event) => setEntryReason(event.target.value)} /></label>{editEntry.isError && <p className="field-error">Confira o valor e a justificativa.</p>}<div className="modal-actions"><button className="ghost" onClick={() => setEditingEntry(null)}>Cancelar</button><button className="primary" disabled={!entryReason.trim() || editEntry.isPending} onClick={() => editEntry.mutate(editingEntry)}>{editEntry.isPending ? "Salvando…" : "Salvar alteração"}</button></div></section></div>}
  </Page>;
}
