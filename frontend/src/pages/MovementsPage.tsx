import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { apiFetch, idempotencyHeaders } from "../api/client";
import type { CashEntry, Page as PageType } from "../api/types";
import { AsyncState } from "../components/AsyncState";
import { MoneyField } from "../components/MoneyField";
import { Page } from "../components/Page";
import { StatementImportModal } from "../components/StatementImportModal";
import { useAccounts, useCards, useCategories } from "../hooks/useFinanceData";
import { formatDateBr } from "../lib/dates";
import { currentMonth, moneyText, requiredText, todayIso } from "../lib/forms";
import { formatBrl, parseBrlToMinor } from "../lib/money";
import { transactionDirection } from "../lib/transactions";

const schema = z.object({ accountId: requiredText, paymentMethod: requiredText, categoryId: z.string(), kind: z.enum(["income", "expense"]), description: requiredText, amount: moneyText, installment: z.boolean(), installmentCount: z.coerce.number().int().min(1, "Informe ao menos uma parcela.").max(120, "O limite é de 120 parcelas."), plannedDate: z.string(), status: z.enum(["planned", "effective"]) }).superRefine((value, context) => {
  if (value.installment && value.installmentCount < 2) context.addIssue({ code: z.ZodIssueCode.custom, path: ["installmentCount"], message: "Informe ao menos duas parcelas." });
});
type Values = z.input<typeof schema>;
type PurchaseInstallment = { id: string; purchase_id: string; description: string; card_id: string; category_id: string | null; purchase_date: string; reference_month: string; due_date: string; installment_number: number; installment_count: number; amount_minor: number; total_minor?: number; purchase_revision: number; purchase_source: string };
type MovementSort = "date-desc" | "date-asc" | "amount-desc" | "amount-asc";
type PeriodMode = "month" | "year";
const movementMonthNames = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const movementMonthShortNames = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

const formatMovementMonth = (value: string) => {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  return match ? `${movementMonthNames[Number(match[2]) - 1]} de ${match[1]}` : value;
};

const monthLabel = (month: string) => {
  if (!month) return "Todo o histórico";
  const [year = new Date().getFullYear(), monthNumber = 1] = month.split("-").map(Number);
  return new Intl.DateTimeFormat("pt-BR", { month: "short", year: "numeric" }).format(new Date(year, monthNumber - 1, 1)).replace(" de ", " ");
};

export function MovementsPage() {
  const queryClient = useQueryClient();
  const accounts = useAccounts();
  const cards = useCards();
  const categories = useCategories();
  const [pageNumber, setPageNumber] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const initialMonth = currentMonth();
  const [dateFrom, setDateFrom] = useState(initialMonth);
  const [dateTo, setDateTo] = useState(initialMonth);
  const [periodMode, setPeriodMode] = useState<PeriodMode>("month");
  const [periodPickerOpen, setPeriodPickerOpen] = useState(false);
  const [pickerYear, setPickerYear] = useState(Number(initialMonth.slice(0, 4)));
  const periodPickerRef = useRef<HTMLDivElement>(null);
  const [accountFilter, setAccountFilter] = useState("");
  const [cardFilter, setCardFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState<"" | "income" | "expense">("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<MovementSort>("date-desc");
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [registering, setRegistering] = useState(false);
  const [importing, setImporting] = useState(false);
  const [editing, setEditing] = useState<CashEntry | null>(null);
  const [editDescription, setEditDescription] = useState("");
  const [editAmount, setEditAmount] = useState("");
  const [editAccountId, setEditAccountId] = useState("");
  const [editCategoryId, setEditCategoryId] = useState("");
  const [editKind, setEditKind] = useState<"income" | "expense">("expense");
  const [editPlannedDate, setEditPlannedDate] = useState("");
  const [editStatus, setEditStatus] = useState<"planned" | "effective">("effective");
  const [editNote, setEditNote] = useState("");
  const [editingPurchase, setEditingPurchase] = useState<PurchaseInstallment | null>(null);
  const [purchaseDescription, setPurchaseDescription] = useState("");
  const [purchaseAmount, setPurchaseAmount] = useState("");
  const [purchaseAccountId, setPurchaseAccountId] = useState("");
  const [purchaseCardId, setPurchaseCardId] = useState("");
  const [purchaseCategoryId, setPurchaseCategoryId] = useState("");
  const [purchaseDate, setPurchaseDate] = useState("");
  const [purchaseInstallmentCount, setPurchaseInstallmentCount] = useState(1);
  const params = new URLSearchParams({ page: "1", page_size: "200", active_only: "true", exclude_investment_yields: "true" });
  const purchaseParams = new URLSearchParams({ page: "1", page_size: "200" });
  if (dateFrom) {
    params.set("date_from", `${dateFrom}-01`);
    purchaseParams.set("date_from", `${dateFrom}-01`);
  }
  if (dateTo) {
    const lastDay = new Date(Number(dateTo.slice(0, 4)), Number(dateTo.slice(5, 7)), 0).getDate();
    const lastDate = `${dateTo}-${String(lastDay).padStart(2, "0")}`;
    params.set("date_to", lastDate);
    purchaseParams.set("date_to", lastDate);
  }
  if (accountFilter) params.set("account_id", accountFilter);
  if (cardFilter) {
    params.set("card_id", cardFilter);
    purchaseParams.set("card_id", cardFilter);
  }
  if (categoryFilter) {
    params.set("category_id", categoryFilter);
    purchaseParams.set("category_id", categoryFilter);
  }
  const hasValidPeriod = !dateFrom || !dateTo || dateFrom <= dateTo;
  const entries = useQuery({ queryKey: ["cash-entries", dateFrom, dateTo, accountFilter, cardFilter, categoryFilter], queryFn: () => apiFetch<PageType<CashEntry>>(`/api/v1/cash-entries?${params}`), enabled: hasValidPeriod, refetchInterval: 60_000 });
  if (accountFilter) purchaseParams.set("account_id", accountFilter);
  const purchases = useQuery({ queryKey: ["purchase-installments", dateFrom, dateTo, accountFilter, cardFilter, categoryFilter], queryFn: () => apiFetch<PageType<PurchaseInstallment>>(`/api/v1/purchase-installments?${purchaseParams}`), enabled: hasValidPeriod, refetchInterval: 60_000 });
  const history = useMemo(() => {
    const cash = (entries.data?.items ?? []).filter((entry) => entry.kind !== "invoice_payment");
    const cardPurchases = (purchases.data?.items ?? [])
      .map<CashEntry>((installment) => ({ id: `installment-${installment.id}`, description: installment.installment_count > 1 ? `${installment.description} (${installment.installment_number}/${installment.installment_count})` : installment.description, kind: "card_purchase", signed_amount_minor: -installment.amount_minor, planned_date: installment.due_date, effective_date: installment.due_date, status: "effective", account_id: cards.data?.items.find((card) => card.id === installment.card_id)?.default_account_id ?? "", card_id: installment.card_id, category_id: installment.category_id, source: "purchase", revision: 1 }));
    return [...cash, ...cardPurchases].sort((a, b) => (b.effective_date ?? b.planned_date).localeCompare(a.effective_date ?? a.planned_date));
  }, [entries.data, purchases.data, cards.data]);
  const filteredHistory = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase("pt-BR");
    const result = history.filter((entry) => {
      const direction = entry.signed_amount_minor >= 0 ? "income" : "expense";
      const category = categories.data?.items.find((item) => item.id === entry.category_id)?.name ?? "Sem categoria";
      const account = accounts.data?.items.find((item) => item.id === entry.account_id);
      const card = cards.data?.items.find((item) => item.id === entry.card_id);
      const searchableText = [entry.description, category, account?.institution, account?.name, card?.name, card ? "cartão" : "pix"].filter(Boolean).join(" ").toLocaleLowerCase("pt-BR");
      return (!typeFilter || direction === typeFilter) && (!normalizedSearch || searchableText.includes(normalizedSearch));
    });
    return result.sort((a, b) => {
      const dateComparison = (a.effective_date ?? a.planned_date).localeCompare(b.effective_date ?? b.planned_date);
      if (sort === "date-asc") return dateComparison;
      if (sort === "date-desc") return -dateComparison;
      if (sort === "amount-asc") return Math.abs(a.signed_amount_minor) - Math.abs(b.signed_amount_minor);
      return Math.abs(b.signed_amount_minor) - Math.abs(a.signed_amount_minor);
    });
  }, [history, search, typeFilter, sort, categories.data, accounts.data, cards.data]);
  const incomeTotal = filteredHistory.reduce((sum, entry) => sum + Math.max(0, entry.signed_amount_minor), 0);
  const expenseTotal = filteredHistory.reduce((sum, entry) => sum + Math.min(0, entry.signed_amount_minor), 0);
  const historyTotal = incomeTotal + expenseTotal;
  const totalPages = Math.max(1, Math.ceil(filteredHistory.length / pageSize));
  const displayedPage = Math.min(pageNumber, totalPages);
  const visibleHistory = filteredHistory.slice((displayedPage - 1) * pageSize, displayedPage * pageSize);
  const firstVisibleItem = filteredHistory.length === 0 ? 0 : (displayedPage - 1) * pageSize + 1;
  const lastVisibleItem = Math.min(displayedPage * pageSize, filteredHistory.length);
  const periodLabel = dateFrom === dateTo ? monthLabel(dateFrom) : `${monthLabel(dateFrom)} – ${monthLabel(dateTo)}`;
  const periodPickerLabel = periodMode === "year" ? dateFrom.slice(0, 4) : formatMovementMonth(dateFrom);
  const selectedYear = dateFrom.slice(0, 4);
  const visibleYears = Array.from({ length: 12 }, (_, index) => pickerYear - 5 + index);
  const activeFilterCount = [accountFilter, cardFilter, categoryFilter, typeFilter].filter(Boolean).length + (dateFrom !== initialMonth || dateTo !== initialMonth ? 1 : 0);
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
  const selectMonth = (month: string) => {
    if (!/^\d{4}-\d{2}$/.test(month)) return;
    setDateFrom(month);
    setDateTo(month);
    setPeriodMode("month");
    setPageNumber(1);
    setPeriodPickerOpen(false);
  };
  const selectYear = (year: string) => {
    if (!/^\d{4}$/.test(year)) return;
    setPickerYear(Number(year));
    setDateFrom(`${year}-01`);
    setDateTo(`${year}-12`);
    setPeriodMode("year");
    setPageNumber(1);
    setPeriodPickerOpen(false);
  };
  useEffect(() => {
    if (!periodPickerOpen) return;
    const closeOnOutsideClick = (event: PointerEvent) => {
      if (!periodPickerRef.current?.contains(event.target as Node)) setPeriodPickerOpen(false);
    };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    return () => document.removeEventListener("pointerdown", closeOnOutsideClick);
  }, [periodPickerOpen]);
  const paginationItems: Array<number | "ellipsis"> = [];
  const visiblePageNumbers = totalPages <= 7
    ? Array.from({ length: totalPages }, (_, index) => index + 1)
    : Array.from(new Set([1, displayedPage - 1, displayedPage, displayedPage + 1, totalPages])).filter((page) => page >= 1 && page <= totalPages).sort((a, b) => a - b);
  visiblePageNumbers.forEach((page, index) => {
    if (index > 0 && page - visiblePageNumbers[index - 1]! > 1) paginationItems.push("ellipsis");
    paginationItems.push(page);
  });
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { accountId: "", paymentMethod: "pix", categoryId: "", kind: "expense", description: "", amount: "", installment: false, installmentCount: 1, plannedDate: todayIso(), status: "effective" } });
  const refresh = () => { for (const key of [["cash-entries"], ["monthly"], ["accounts"], ["cards"], ["invoices"], ["purchases"], ["purchase-installments"]]) void queryClient.invalidateQueries({ queryKey: key }); };
  const save = useMutation({ mutationFn: async (value: z.output<typeof schema>) => {
    const installmentCount = value.installment ? value.installmentCount : 1;
    if (value.paymentMethod !== "pix") {
      const purchase = { card_id: value.paymentMethod, category_id: value.categoryId || null, description: value.description, purchase_date: value.plannedDate, total_minor: value.amount, installment_count: installmentCount, first_invoice_month: null };
      const preview = await apiFetch<{ preview_token: string }>("/api/v1/purchases/preview", { method: "POST", body: JSON.stringify(purchase) });
      return apiFetch("/api/v1/purchases", { method: "POST", headers: idempotencyHeaders(), body: JSON.stringify({ ...purchase, preview_token: preview.preview_token }) });
    }
    return apiFetch("/api/v1/cash-entries/installments", { method: "POST", headers: idempotencyHeaders(), body: JSON.stringify({ account_id: value.accountId, category_id: value.categoryId || null, kind: value.kind, description: value.description, amount_minor: value.amount, installment_count: installmentCount, planned_date: value.plannedDate, effective_date: value.status === "effective" ? value.plannedDate : null, status: value.status, note: null }) });
  }, onSuccess: () => { form.reset(); setRegistering(false); refresh(); } });
  const correct = useMutation({ mutationFn: (entry: CashEntry) => apiFetch(`/api/v1/cash-entries/${entry.id}`, { method: "PUT", body: JSON.stringify({ account_id: editAccountId, category_id: editCategoryId || null, kind: editKind, description: editDescription, amount_minor: parseBrlToMinor(editAmount), planned_date: editPlannedDate, effective_date: editStatus === "effective" ? editPlannedDate : null, status: editStatus, note: editNote.trim() || null, expected_revision: entry.revision }) }), onSuccess: () => { setEditing(null); refresh(); } });
  const remove = useMutation({
    mutationFn: (entry: CashEntry) => apiFetch(`/api/v1/cash-entries/${entry.id}/${entry.status === "planned" ? "cancelled" : "voided"}`, { method: "POST", body: JSON.stringify({ expected_revision: entry.revision, reason: "Exclusão solicitada pelo usuário" }) }),
    onSuccess: () => { setEditing(null); refresh(); },
  });
  const updatePurchase = useMutation({
    mutationFn: (purchase: PurchaseInstallment) => apiFetch(`/api/v1/purchases/${purchase.purchase_id}`, { method: "PUT", body: JSON.stringify({ card_id: purchaseCardId, category_id: purchaseCategoryId || null, description: purchaseDescription, purchase_date: purchaseDate, total_minor: parseBrlToMinor(purchaseAmount), installment_count: purchaseInstallmentCount, first_invoice_month: null, expected_revision: purchase.purchase_revision }) }),
    onSuccess: () => { setEditingPurchase(null); refresh(); },
  });
  const kind = form.watch("kind");
  const installment = form.watch("installment");
  const selectedAccountId = form.watch("accountId");
  const availableCards = cards.data?.items.filter((card) => card.default_account_id === selectedAccountId) ?? [];
  const availablePurchaseCards = cards.data?.items.filter((card) => card.default_account_id === purchaseAccountId) ?? [];
  const startEditingPurchase = (purchase: PurchaseInstallment) => {
    const card = cards.data?.items.find((item) => item.id === purchase.card_id);
    setEditingPurchase(purchase);
    setPurchaseDescription(purchase.description);
    const totalMinor = purchase.total_minor ?? purchase.amount_minor * purchase.installment_count;
    setPurchaseAmount((totalMinor / 100).toFixed(2).replace(".", ","));
    setPurchaseAccountId(card?.default_account_id ?? "");
    setPurchaseCardId(purchase.card_id);
    setPurchaseCategoryId(purchase.category_id ?? "");
    setPurchaseDate(purchase.purchase_date);
    setPurchaseInstallmentCount(purchase.installment_count);
  };
  const startEditing = (entry: CashEntry) => {
    setEditing(entry);
    setEditAccountId(entry.account_id);
    setEditCategoryId(entry.category_id ?? "");
    setEditKind(entry.kind === "income" ? "income" : "expense");
    setEditDescription(entry.description);
    setEditAmount((Math.abs(entry.signed_amount_minor) / 100).toFixed(2).replace(".", ","));
    setEditPlannedDate(entry.planned_date);
    setEditStatus(entry.status === "planned" ? "planned" : "effective");
    setEditNote(entry.note ?? "");
  };
  return <Page title="Histórico de Transações">
    <section className="panel movement-history transactions-history">
    <div className="transactions-heading-area">
    <div className="panel-heading transactions-history-heading">
      <div><h2>Lançamentos</h2><p>{periodLabel} · {filteredHistory.length} {filteredHistory.length === 1 ? "registro" : "registros"}</p></div>
      <div className="transactions-history-toolbar">
        <button className="transactions-toolbar-button" type="button" aria-expanded={filtersOpen} onClick={() => setFiltersOpen((value) => !value)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h10M18 7h2M14 4v6M4 17h2M10 17h10M10 14v6"/></svg>Filtros{activeFilterCount > 0 && <span className="filter-count">{activeFilterCount}</span>}</button>
        <button className="transactions-toolbar-button" type="button" onClick={() => setImporting(true)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M12 18v-6M9 15l3 3 3-3"/></svg>Importar extrato</button>
        <button className="primary overview-new-transaction transactions-new-button" type="button" onClick={() => setRegistering(true)}><span aria-hidden="true">＋</span> Nova transação</button>
      </div>
    </div>
    {filtersOpen && <div className="movement-filter" aria-label="Filtros do histórico">
      <div className="overview-filter-fields">
        <div className="investment-date-filter movement-date-filter" ref={periodPickerRef}>
          <span className="investment-date-filter-label">Período</span>
          <button className="investment-date-trigger" type="button" aria-haspopup="dialog" aria-expanded={periodPickerOpen} onClick={() => setPeriodPickerOpen((open) => !open)}><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg><span>{periodPickerLabel}</span><svg className="investment-date-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg></button>
          {periodPickerOpen && <div className="investment-date-popover" role="dialog" aria-label="Selecionar período">
            <div className="investment-date-popover-value"><span>{periodPickerLabel}</span><button type="button" aria-label="Fechar seletor de período" onClick={() => setPeriodPickerOpen(false)}>×</button></div>
            <div className="investment-period-toggle" role="group" aria-label="Visualizar por mês ou ano"><button type="button" className={periodMode === "month" ? "active" : ""} aria-pressed={periodMode === "month"} onClick={() => selectPeriodMode("month")}>Mês</button><button type="button" className={periodMode === "year" ? "active" : ""} aria-pressed={periodMode === "year"} onClick={() => selectPeriodMode("year")}>Ano</button></div>
            <div className="investment-period-shortcuts" aria-label="Atalhos de período"><button type="button" onClick={() => selectMonth(initialMonth)}>Mês atual</button><button type="button" onClick={() => { const date = new Date(Number(initialMonth.slice(0, 4)), Number(initialMonth.slice(5, 7)) - 2, 1); selectMonth(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`); }}>Mês anterior</button><button type="button" onClick={() => selectYear(initialMonth.slice(0, 4))}>Ano atual</button></div>
            {periodMode === "month" ? <><div className="investment-date-navigation"><button type="button" aria-label="Ano anterior" onClick={() => setPickerYear((year) => year - 1)}>‹</button><strong>{pickerYear}</strong><button type="button" aria-label="Próximo ano" onClick={() => setPickerYear((year) => year + 1)}>›</button></div><div className="investment-month-grid">{movementMonthShortNames.map((month, index) => { const value = `${pickerYear}-${String(index + 1).padStart(2, "0")}`; return <button type="button" key={month} className={dateFrom === value && dateTo === value ? "selected" : ""} aria-pressed={dateFrom === value && dateTo === value} onClick={() => selectMonth(value)}>{month}</button>; })}</div></> : <><div className="investment-date-navigation"><button type="button" aria-label="Anos anteriores" onClick={() => setPickerYear((year) => year - 12)}>‹</button><strong>{visibleYears[0]}–{visibleYears[visibleYears.length - 1]}</strong><button type="button" aria-label="Próximos anos" onClick={() => setPickerYear((year) => year + 12)}>›</button></div><div className="investment-year-grid">{visibleYears.map((year) => <button type="button" key={year} className={selectedYear === String(year) ? "selected" : ""} aria-pressed={selectedYear === String(year)} onClick={() => selectYear(String(year))}>{year}</button>)}</div></>}
          </div>}
        </div>
        <label className="field"><span>Conta</span><select value={accountFilter} onChange={(event) => { setAccountFilter(event.target.value); setPageNumber(1); }}><option value="">Todas as contas</option>{accounts.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Cartão</span><select value={cardFilter} onChange={(event) => { setCardFilter(event.target.value); setPageNumber(1); }}><option value="">Todos os cartões</option>{cards.data?.items.map((item) => { const account = accounts.data?.items.find((candidate) => candidate.id === item.default_account_id); const bank = account?.institution ?? account?.name; return <option key={item.id} value={item.id}>{bank ? `${item.name} (${bank})` : item.name}</option>; })}</select></label>
        <label className="field"><span>Categoria</span><select value={categoryFilter} onChange={(event) => { setCategoryFilter(event.target.value); setPageNumber(1); }}><option value="">Todas as categorias</option>{categories.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Tipo</span><select value={typeFilter} onChange={(event) => { setTypeFilter(event.target.value as "" | "income" | "expense"); setPageNumber(1); }}><option value="">Entradas e despesas</option><option value="income">Entradas</option><option value="expense">Despesas</option></select></label>
      </div>
    </div>}
    </div>
    {!hasValidPeriod && <p className="field-error" role="alert">A data inicial deve ser anterior ou igual à data final.</p>}
    <AsyncState loading={entries.isPending || purchases.isPending} error={entries.isError || purchases.isError} empty={history.length === 0}>
      <div className="investment-period-summary movement-summary-cards" aria-label="Resumo do período">
        <div className="income"><span><i aria-hidden="true">↗</i> Entradas</span><strong className="positive">+ {formatBrl(incomeTotal)}</strong></div>
        <div className="withdrawal"><span><i aria-hidden="true">↘</i> Saídas</span><strong className="negative">− {formatBrl(Math.abs(expenseTotal))}</strong></div>
        <div className="net"><span><i aria-hidden="true">=</i> Saldo</span><strong className={historyTotal < 0 ? "negative" : "positive"}>{historyTotal >= 0 ? "+ " : ""}{formatBrl(historyTotal)}</strong></div>
      </div>
      <div className="movement-list-controls">
        <label className="movement-search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg><span className="sr-only">Buscar transação</span><input type="search" placeholder="Buscar por descrição, categoria ou banco" value={search} onChange={(event) => { setSearch(event.target.value); setPageNumber(1); }} /></label>
        <label className="movement-sort"><span>Ordenar por</span><select value={sort} onChange={(event) => { setSort(event.target.value as MovementSort); setPageNumber(1); }}><option value="date-desc">Mais recentes</option><option value="date-asc">Mais antigas</option><option value="amount-desc">Maior valor</option><option value="amount-asc">Menor valor</option></select></label>
      </div>
      {filteredHistory.length === 0 ? <div className="movement-no-results"><strong>Nenhum lançamento encontrado</strong><span>Tente alterar a busca ou os filtros selecionados.</span></div> : <>
        <div className="movement-list" role="table" aria-label="Lançamentos do período">
          <div className="movement-list-header" role="row"><span role="columnheader">Registro</span><span role="columnheader">Tipo</span><span role="columnheader">Categoria</span><span role="columnheader">Banco</span><span role="columnheader">Forma de pagamento</span><span role="columnheader">Data</span><span role="columnheader">Valor</span></div>
          <div role="rowgroup">{visibleHistory.map((entry) => { const account = accounts.data?.items.find((item) => item.id === entry.account_id); const card = cards.data?.items.find((item) => item.id === entry.card_id); const category = categories.data?.items.find((item) => item.id === entry.category_id)?.name ?? "Sem categoria"; const purchase = entry.source === "purchase" ? purchases.data?.items.find((item) => `installment-${item.id}` === entry.id) : undefined; const editableSources = ["manual", "file_import", "bank_api"]; const canEdit = (editableSources.includes(entry.source) && ["income", "expense", "balance_adjustment"].includes(entry.kind)) || (purchase && editableSources.includes(purchase.purchase_source)); const direction = transactionDirection(entry.kind, entry.signed_amount_minor); return <article className="movement-row" role="row" key={entry.id}><strong role="cell" title={`Origem: ${{ manual: "Manual", bank_api: "Integração bancária", file_import: "CSV/OFX" }[purchase?.purchase_source ?? entry.source] ?? entry.source}`}>{entry.description}</strong><span role="cell"><span className={`movement-kind ${entry.signed_amount_minor < 0 ? "expense" : "income"}`}>{direction}</span></span><span role="cell" data-label="Categoria">{category}</span><span role="cell" data-label="Banco" title={account?.name}>{account?.institution ?? account?.name ?? "—"}</span><span role="cell" data-label="Pagamento">{card?.name ?? "Pix"}</span><time role="cell" data-label="Data" dateTime={entry.effective_date ?? entry.planned_date}>{formatDateBr(entry.effective_date ?? entry.planned_date)}</time><span role="cell" data-label="Valor" className={`movement-value ${entry.signed_amount_minor < 0 ? "negative" : "positive"}`}>{formatBrl(entry.signed_amount_minor)}</span><span role="cell" className="movement-action"><button type="button" className="movement-edit-button" disabled={!canEdit} aria-label={`Editar ${entry.description}`} title={canEdit ? "Editar registro" : "Este registro não pode ser editado manualmente"} onClick={() => { if (purchase) { startEditingPurchase(purchase); return; } startEditing(entry); }}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button></span></article>; })}</div>
        </div>
        <nav className="pagination investment-pagination" aria-label="Paginação do histórico"><div className="investment-pagination-summary"><span>Exibindo {firstVisibleItem}–{lastVisibleItem} de {filteredHistory.length}</span><label><span className="sr-only">Itens por página</span><select aria-label="Itens por página" value={pageSize} onChange={(event) => { setPageSize(Number(event.target.value)); setPageNumber(1); }}>{[10, 15, 20, 25, 50].map((size) => <option key={size} value={size}>{size} / página</option>)}</select></label></div><div className="investment-pagination-navigation"><button className="pagination-direction previous" type="button" disabled={displayedPage === 1} onClick={() => setPageNumber(displayedPage - 1)}><span aria-hidden="true">‹</span> Anterior</button><div className="investment-pagination-pages">{paginationItems.map((item, index) => item === "ellipsis" ? <span className="pagination-ellipsis" key={`ellipsis-${index}`}>…</span> : <button type="button" key={item} className={item === displayedPage ? "active" : ""} aria-current={item === displayedPage ? "page" : undefined} aria-label={`Ir para a página ${item}`} onClick={() => setPageNumber(item)}>{item}</button>)}</div><button className="pagination-direction next" type="button" disabled={displayedPage === totalPages} onClick={() => setPageNumber(displayedPage + 1)}>Próxima <span aria-hidden="true">›</span></button></div></nav>
      </>}
    </AsyncState></section>
    {importing && <StatementImportModal onClose={() => setImporting(false)} />}
    {registering && <div className="modal-backdrop"><section className="modal transaction-modal" role="dialog" aria-modal="true" aria-labelledby="register-movement-title">
      <h2 id="register-movement-title">Nova Transação</h2>
      <form onSubmit={form.handleSubmit((value) => save.mutate(schema.parse(value)))}>
        <label className="field"><span>Tipo</span><select {...form.register("kind", { onChange: (event) => { if (event.target.value !== "expense") form.setValue("paymentMethod", "pix"); } })}><option value="expense">Despesa</option><option value="income">Receita</option></select></label>
        <label className="field"><span>Descrição</span><input {...form.register("description")} />{form.formState.errors.description && <small className="field-error">{form.formState.errors.description.message}</small>}</label>
        <div className="installment-row"><MoneyField label="Valor total" registration={form.register("amount")} error={form.formState.errors.amount} /><label className="installment-toggle"><span>Parcelado</span><input type="checkbox" {...form.register("installment", { onChange: (event) => { if (!event.target.checked) form.setValue("installmentCount", 1); } })} /></label><label className="field"><span>Número de parcelas</span><input type="number" min="2" max="120" disabled={!installment} {...form.register("installmentCount")} />{form.formState.errors.installmentCount && <small className="field-error">{form.formState.errors.installmentCount.message}</small>}</label></div>
        <label className="field"><span>Conta</span><select {...form.register("accountId", { onChange: () => form.setValue("paymentMethod", "pix") })}><option value="">Selecione</option>{accounts.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>Meio de pagamento</span><select {...form.register("paymentMethod")}><option value="pix">Pix</option>{kind === "expense" && availableCards.map((card) => <option key={card.id} value={card.id}>{card.name}</option>)}</select></label>
        <label className="field"><span>Categoria (opcional)</span><select {...form.register("categoryId")}><option value="">Sem categoria</option>{categories.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
        <label className="field"><span>{installment ? "Data da primeira parcela" : "Data"}</span><input type="date" {...form.register("plannedDate")} /></label><input type="hidden" {...form.register("status")} />
        {save.isError && <p className="field-error" role="alert">Não foi possível salvar o registro.</p>}
        <div className="modal-actions"><button type="button" className="ghost overview-new-transaction" onClick={() => setRegistering(false)}>Cancelar</button><button className="primary overview-new-transaction" disabled={save.isPending}>Salvar</button></div>
      </form>
    </section></div>}
    {editingPurchase && <div className="modal-backdrop"><section className="modal transaction-modal transaction-edit-modal" role="dialog" aria-modal="true" aria-labelledby="edit-purchase-title"><h2 id="edit-purchase-title">Editar transação</h2><p>A alteração atualiza todas as parcelas ainda não liquidadas e fica registrada na auditoria.</p><label className="field"><span>Tipo</span><select value="expense" disabled><option value="expense">Despesa</option></select></label><label className="field"><span>Descrição</span><input value={purchaseDescription} onChange={(event) => setPurchaseDescription(event.target.value)} /></label><div className="field-row"><label className="field"><span>Valor total</span><div className="money-control"><span>R$</span><input inputMode="decimal" value={purchaseAmount} onChange={(event) => setPurchaseAmount(event.target.value)} /></div></label><label className="field"><span>Número de parcelas</span><input type="number" min="1" max="120" value={purchaseInstallmentCount} onChange={(event) => setPurchaseInstallmentCount(Number(event.target.value))} /></label></div><label className="field"><span>Conta</span><select value={purchaseAccountId} onChange={(event) => { setPurchaseAccountId(event.target.value); setPurchaseCardId(""); }}><option value="">Selecione</option>{accounts.data?.items.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label><label className="field"><span>Meio de pagamento</span><select value={purchaseCardId} onChange={(event) => setPurchaseCardId(event.target.value)}><option value="">Selecione</option>{availablePurchaseCards.map((card) => <option key={card.id} value={card.id}>{card.name}</option>)}</select></label><label className="field"><span>Categoria (opcional)</span><select value={purchaseCategoryId} onChange={(event) => setPurchaseCategoryId(event.target.value)}><option value="">Sem categoria</option>{categories.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>Data da compra</span><input type="date" value={purchaseDate} onChange={(event) => setPurchaseDate(event.target.value)} /></label>{updatePurchase.isError && <p className="field-error">Confira os dados. Compras com faturas liquidadas não podem ser alteradas.</p>}<div className="modal-actions"><button className="ghost overview-new-transaction" disabled={updatePurchase.isPending} onClick={() => setEditingPurchase(null)}>Cancelar</button><button className="primary overview-new-transaction" disabled={!purchaseDescription.trim() || !purchaseAmount.trim() || !purchaseAccountId || !purchaseCardId || !purchaseDate || purchaseInstallmentCount < 1 || purchaseInstallmentCount > 120 || updatePurchase.isPending} onClick={() => updatePurchase.mutate(editingPurchase)}>{updatePurchase.isPending ? "Salvando…" : "Salvar"}</button></div></section></div>}
    {editing && <div className="modal-backdrop"><section className="modal transaction-modal transaction-edit-modal" role="dialog" aria-modal="true" aria-labelledby="edit-transaction-title"><h2 id="edit-transaction-title">Editar transação</h2><p>A alteração ou exclusão guarda o histórico na auditoria.</p><div className="field-row"><label className="field"><span>Tipo</span><select value={editKind} onChange={(event) => setEditKind(event.target.value as "income" | "expense")}><option value="expense">Despesa</option><option value="income">Receita</option></select></label><label className="field"><span>Estado</span><select value={editStatus} onChange={(event) => setEditStatus(event.target.value as "planned" | "effective")}><option value="effective">Efetivado</option><option value="planned">Previsto</option></select></label></div><label className="field"><span>Descrição</span><input value={editDescription} onChange={(event) => setEditDescription(event.target.value)} /></label><div className="field-row"><label className="field"><span>Valor</span><div className="money-control"><span>R$</span><input inputMode="decimal" value={editAmount} onChange={(event) => setEditAmount(event.target.value)} /></div></label><label className="field"><span>Data</span><input type="date" value={editPlannedDate} onChange={(event) => setEditPlannedDate(event.target.value)} /></label></div><label className="field"><span>Conta</span><select value={editAccountId} onChange={(event) => setEditAccountId(event.target.value)}>{accounts.data?.items.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}</select></label><label className="field"><span>Categoria (opcional)</span><select value={editCategoryId} onChange={(event) => setEditCategoryId(event.target.value)}><option value="">Sem categoria</option>{categories.data?.items.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}</select></label><label className="field"><span>Observação (opcional)</span><input value={editNote} onChange={(event) => setEditNote(event.target.value)} /></label>{(correct.isError || remove.isError) && <p className="field-error">Confira os dados informados.</p>}<div className="modal-actions"><button className="danger overview-new-transaction" disabled={correct.isPending || remove.isPending} onClick={() => { if (window.confirm(`Excluir o registro ${editing.description}?`)) remove.mutate(editing); }}>{remove.isPending ? "Excluindo…" : "Excluir registro"}</button><button className="ghost overview-new-transaction" disabled={correct.isPending || remove.isPending} onClick={() => setEditing(null)}>Cancelar</button><button className="primary overview-new-transaction" disabled={!editAccountId || !editDescription.trim() || !editAmount.trim() || !editPlannedDate || correct.isPending || remove.isPending} onClick={() => correct.mutate(editing)}>{correct.isPending ? "Salvando…" : "Salvar alteração"}</button></div></section></div>}
  </Page>;
}
