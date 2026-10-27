import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { useForm } from "react-hook-form";
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
type CategorySort = "amount-desc" | "amount-asc" | "name";
type PeriodMode = "month" | "year";

const monthNames = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"];
const monthShortNames = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];
const formatMonth = (value: string) => {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  return match ? `${monthNames[Number(match[2]) - 1]} de ${match[1]}` : value;
};

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
  const [search, setSearch] = useState("");
  const [periodMode, setPeriodMode] = useState<PeriodMode>("month");
  const [periodPickerOpen, setPeriodPickerOpen] = useState(false);
  const [pickerYear, setPickerYear] = useState(Number(initialMonth.slice(0, 4)));
  const periodPickerRef = useRef<HTMLDivElement>(null);
  const [sort, setSort] = useState<CategorySort>("amount-desc");
  const [registering, setRegistering] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
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
  const totalSpent = useMemo(() => (categories.data?.items ?? []).reduce((sum, category) => sum + (spentByCategory.get(category.id) ?? 0), 0), [categories.data, spentByCategory]);
  const visibleCategories = useMemo(() => {
    const normalizedSearch = search.trim().toLocaleLowerCase("pt-BR");
    const items = (categories.data?.items ?? []).filter((category) => !normalizedSearch || category.name.toLocaleLowerCase("pt-BR").includes(normalizedSearch));
    return items.sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name, "pt-BR");
      const difference = (spentByCategory.get(a.id) ?? 0) - (spentByCategory.get(b.id) ?? 0);
      return sort === "amount-asc" ? difference : -difference;
    });
  }, [categories.data, search, sort, spentByCategory]);
  const activeFilterCount = Number(Boolean(accountFilter)) + Number(Boolean(cardFilter));
  const periodLabel = dateFrom === dateTo ? formatMonth(dateFrom) : `${formatMonth(dateFrom)} — ${formatMonth(dateTo)}`;
  const selectedYear = dateFrom.slice(0, 4);
  const periodPickerLabel = periodMode === "year" ? selectedYear : periodLabel;
  const selectPeriodMode = (mode: PeriodMode) => {
    setPeriodMode(mode);
    if (mode === "month") {
      const month = pickerYear === Number(initialMonth.slice(0, 4)) ? initialMonth.slice(5, 7) : "01";
      setDateFrom(`${pickerYear}-${month}`);
      setDateTo(`${pickerYear}-${month}`);
    } else {
      setDateFrom(`${pickerYear}-01`);
      setDateTo(`${pickerYear}-12`);
    }
  };
  const selectMonth = (month: string) => { if (/^\d{4}-\d{2}$/.test(month)) { setDateFrom(month); setDateTo(month); setPeriodPickerOpen(false); } };
  const selectYear = (year: string) => {
    if (!/^\d{4}$/.test(year)) return;
    setPickerYear(Number(year));
    setDateFrom(`${year}-01`);
    setDateTo(`${year}-12`);
    setPeriodPickerOpen(false);
  };
  const visibleYears = Array.from({ length: 12 }, (_, index) => pickerYear - 5 + index);
  useEffect(() => {
    if (!periodPickerOpen) return;
    const closeOnOutsideClick = (event: PointerEvent) => { if (!periodPickerRef.current?.contains(event.target as Node)) setPeriodPickerOpen(false); };
    const closeOnEscape = (event: KeyboardEvent) => { if (event.key === "Escape") setPeriodPickerOpen(false); };
    document.addEventListener("pointerdown", closeOnOutsideClick);
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.removeEventListener("pointerdown", closeOnOutsideClick); document.removeEventListener("keydown", closeOnEscape); };
  }, [periodPickerOpen]);
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["categories"] });
  const save = useMutation({
    mutationFn: (value: Values) => apiFetch("/api/v1/categories", { method: "POST", body: JSON.stringify(value) }),
    onSuccess: () => { form.reset(); setRegistering(false); refresh(); },
  });
  const rename = useMutation({
    mutationFn: (item: Category) => apiFetch(`/api/v1/categories/${item.id}`, { method: "PUT", body: JSON.stringify({ name, expected_revision: item.revision }) }),
    onSuccess: () => { setEditing(null); refresh(); },
  });
  const remove = useMutation({
    mutationFn: (item: Category) => apiFetch(`/api/v1/categories/${item.id}`, { method: "DELETE", body: JSON.stringify({ expected_revision: item.revision, reason: "Excluída definitivamente pelo usuário" }) }),
    onSuccess: () => { setEditing(null); setConfirmingDelete(false); refresh(); },
  });

  return <Page title="Gastos por categoria" actions={<button className="primary overview-new-transaction categories-new-button" type="button" onClick={() => setRegistering(true)}><span aria-hidden="true">＋</span> Nova categoria</button>}>
    <section className="panel movement-history categories-history">
      <div className="transactions-heading-area categories-heading-area">
        <div className="panel-heading transactions-history-heading categories-filter-anchor"><div></div></div>
        {filtersOpen && <div className="movement-filter" aria-label="Filtros das categorias"><div className="overview-filter-fields">
          <div className="investment-date-filter movement-date-filter" ref={periodPickerRef}>
            <span className="investment-date-filter-label">Período</span>
            <button className="investment-date-trigger" type="button" aria-haspopup="dialog" aria-expanded={periodPickerOpen} onClick={() => setPeriodPickerOpen((open) => !open)}><svg viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/></svg><span>{periodPickerLabel}</span><svg className="investment-date-chevron" viewBox="0 0 24 24" aria-hidden="true"><path d="m7 10 5 5 5-5"/></svg></button>
            {periodPickerOpen && <div className="investment-date-popover" role="dialog" aria-label="Selecionar período">
              <div className="investment-date-popover-value"><span>{periodPickerLabel}</span><button type="button" aria-label="Fechar seletor de período" onClick={() => setPeriodPickerOpen(false)}>×</button></div>
              <div className="investment-period-toggle" role="group" aria-label="Visualizar por mês ou ano"><button type="button" className={periodMode === "month" ? "active" : ""} aria-pressed={periodMode === "month"} onClick={() => selectPeriodMode("month")}>Mês</button><button type="button" className={periodMode === "year" ? "active" : ""} aria-pressed={periodMode === "year"} onClick={() => selectPeriodMode("year")}>Ano</button></div>
              <div className="investment-period-shortcuts" aria-label="Atalhos de período"><button type="button" onClick={() => selectMonth(initialMonth)}>Mês atual</button><button type="button" onClick={() => { const date = new Date(Number(initialMonth.slice(0, 4)), Number(initialMonth.slice(5, 7)) - 2, 1); selectMonth(`${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`); }}>Mês anterior</button><button type="button" onClick={() => selectYear(initialMonth.slice(0, 4))}>Ano atual</button></div>
              {periodMode === "month" ? <><div className="investment-date-navigation"><button type="button" aria-label="Ano anterior" onClick={() => setPickerYear((year) => year - 1)}>‹</button><strong>{pickerYear}</strong><button type="button" aria-label="Próximo ano" onClick={() => setPickerYear((year) => year + 1)}>›</button></div><div className="investment-month-grid">{monthShortNames.map((month, index) => { const value = `${pickerYear}-${String(index + 1).padStart(2, "0")}`; return <button type="button" key={month} className={dateFrom === value && dateTo === value ? "selected" : ""} aria-pressed={dateFrom === value && dateTo === value} onClick={() => selectMonth(value)}>{month}</button>; })}</div></> : <><div className="investment-date-navigation"><button type="button" aria-label="Anos anteriores" onClick={() => setPickerYear((year) => year - 12)}>‹</button><strong>{visibleYears[0]}–{visibleYears[visibleYears.length - 1]}</strong><button type="button" aria-label="Próximos anos" onClick={() => setPickerYear((year) => year + 12)}>›</button></div><div className="investment-year-grid">{visibleYears.map((year) => <button type="button" key={year} className={selectedYear === String(year) ? "selected" : ""} aria-pressed={selectedYear === String(year)} onClick={() => selectYear(String(year))}>{year}</button>)}</div></>}
            </div>}
          </div>
          <label className="field"><span>Conta</span><select value={accountFilter} onChange={(event) => setAccountFilter(event.target.value)}><option value="">Todas as contas</option>{accounts.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="field"><span>Cartão</span><select value={cardFilter} onChange={(event) => setCardFilter(event.target.value)}><option value="">Todos os cartões</option>{cards.data?.items.map((item) => { const account = accounts.data?.items.find((candidate) => candidate.id === item.default_account_id); const bank = account?.institution ?? account?.name; return <option key={item.id} value={item.id}>{bank ? `${item.name} (${bank})` : item.name}</option>; })}</select></label>
        </div></div>}
      </div>
      {!hasValidPeriod && <p className="field-error" role="alert">A data inicial deve ser anterior ou igual à data final.</p>}
      <AsyncState loading={categories.isPending || accounts.isPending || cards.isPending || report.isPending} error={categories.isError || accounts.isError || cards.isError || report.isError} empty={!categories.data?.items.length}>
        <div className="movement-list-controls categories-list-controls"><label className="movement-search"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/></svg><span className="sr-only">Buscar categoria</span><input type="search" placeholder="Buscar por categoria" value={search} onChange={(event) => setSearch(event.target.value)} /></label><div className="categories-list-actions"><label className="movement-sort"><span>Ordenar por</span><select value={sort} onChange={(event) => setSort(event.target.value as CategorySort)}><option value="amount-desc">Maior gasto</option><option value="amount-asc">Menor gasto</option><option value="name">Nome</option></select></label><button className="transactions-toolbar-button" type="button" aria-expanded={filtersOpen} onClick={() => setFiltersOpen((value) => !value)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h10M18 7h2M14 4v6M4 17h2M10 17h10M10 14v6"/></svg>Filtros{activeFilterCount > 0 && <span className="filter-count">{activeFilterCount}</span>}</button></div></div>
        {visibleCategories.length === 0 ? <div className="movement-no-results"><strong>Nenhuma categoria encontrada</strong><span>Tente alterar a busca informada.</span></div> : <div className="movement-list">
          <div className="movement-list-header" aria-hidden="true"><span>Categoria</span><span>Participação</span><span>Gasto no período</span></div>
          {visibleCategories.map((category) => {
            const spent = spentByCategory.get(category.id) ?? 0;
            const percentage = totalSpent ? spent / totalSpent * 100 : 0;
            return <Fragment key={category.id}>
              <article className="movement-row category-summary-row">
                <div className="category-expand-button category-details">
                  <strong>{category.name}</strong>
                  <span className="category-share"><span className="category-share-track" aria-hidden="true"><i style={{ width: `${Math.min(percentage, 100)}%` }}/></span><small>{new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(percentage)}%</small></span>
                  <span className={`category-amount${spent === 0 ? " muted" : ""}`}>{formatBrl(spent)}</span>
                </div>
                <button type="button" className="movement-edit-button" aria-label={`Editar categoria ${category.name}`} title="Editar categoria" onClick={() => { setEditing(category); setName(category.name); setConfirmingDelete(false); }}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button>
              </article>
            </Fragment>;
          })}
        </div>}
      </AsyncState>
    </section>

    {registering && <div className="modal-backdrop"><form className="modal form-panel transaction-modal" role="dialog" aria-modal="true" aria-labelledby="new-category-title" onSubmit={form.handleSubmit((value) => save.mutate(value))}>
      <h2 id="new-category-title">Nova categoria</h2>
      <label className="field"><span>Nome</span><input required {...form.register("name")} /></label>
      {save.isError && <p className="field-error" role="alert">Não foi possível salvar a categoria.</p>}
      <div className="modal-actions"><button type="button" className="ghost overview-new-transaction" onClick={() => setRegistering(false)}>Cancelar</button><button className="primary overview-new-transaction" disabled={save.isPending}>{save.isPending ? "Salvando…" : "Salvar"}</button></div>
    </form></div>}

    {editing && <div className="modal-backdrop"><form className="modal form-panel transaction-modal" role="dialog" aria-modal="true" aria-labelledby="rename-category-title" onSubmit={(event) => { event.preventDefault(); if (name.trim()) rename.mutate(editing); }}>
      <h2 id="rename-category-title">Editar categoria</h2>
      <label className="field"><span>Novo nome</span><input required autoFocus value={name} onChange={(event) => setName(event.target.value)} /></label>
      {rename.isError && <p className="field-error" role="alert">Não foi possível renomear a categoria.</p>}
      {remove.isError && <p className="field-error" role="alert">Não foi possível deletar a categoria.</p>}
      <div className="modal-actions"><button type="button" className="ghost overview-new-transaction" disabled={rename.isPending || remove.isPending} onClick={() => { setEditing(null); setConfirmingDelete(false); }}>Cancelar</button><button type="button" className="danger overview-new-transaction category-danger-button" disabled={rename.isPending || remove.isPending} onClick={() => setConfirmingDelete(true)}>Deletar</button><button className="primary overview-new-transaction" disabled={!name.trim() || rename.isPending || remove.isPending}>{rename.isPending ? "Salvando…" : "Salvar"}</button></div>
    </form></div>}

    {editing && confirmingDelete && <div className="modal-backdrop category-delete-backdrop"><form className="modal form-panel transaction-modal category-delete-modal" role="alertdialog" aria-modal="true" aria-labelledby="delete-category-title" aria-describedby="delete-category-description" onSubmit={(event) => { event.preventDefault(); remove.mutate(editing); }}><h2 id="delete-category-title">Confirmar exclusão</h2><div className="category-delete-warning"><strong>A categoria “{editing.name}” será apagada do sistema.</strong><p id="delete-category-description">Esta ação não pode ser desfeita. Os lançamentos existentes serão preservados e ficarão sem categoria.</p></div>{remove.isError && <p className="field-error" role="alert">Não foi possível deletar a categoria.</p>}<div className="modal-actions category-delete-modal-actions"><button type="button" className="secondary overview-new-transaction" disabled={remove.isPending} onClick={() => setConfirmingDelete(false)}>Cancelar</button><button className="danger overview-new-transaction category-danger-button" disabled={remove.isPending}>{remove.isPending ? "Deletando…" : "Confirmar exclusão"}</button></div></form></div>}
  </Page>;
}
