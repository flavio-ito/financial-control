import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { apiFetch, idempotencyHeaders } from "../api/client";
import type { Account, Card } from "../api/types";
import { AsyncState } from "../components/AsyncState";
import { MoneyField } from "../components/MoneyField";
import { Page } from "../components/Page";
import { useAccounts, useCards } from "../hooks/useFinanceData";
import { moneyText, requiredText, todayIso } from "../lib/forms";
import { formatBrl } from "../lib/money";

const accountSchema = z.object({ name: requiredText, institution: z.string(), balance: moneyText, referenceDate: z.string() });
const cardDay = z.string().regex(/^(?:[1-9]|[12][0-9]|3[01])$/, "Informe um dia entre 1 e 31.").transform(Number);
const cardSchema = z.object({ name: requiredText, accountId: requiredText, spent: moneyText, closingDay: cardDay, dueDay: cardDay });
type CardFormValues = z.input<typeof cardSchema>;
const emptyCard: CardFormValues = { name: "", accountId: "", spent: "", closingDay: "", dueDay: "" };
type Invoice = { id: string; card_id: string; reference_month: string; due_date: string; state: "open" | "closed" | "settled"; payable_minor: number; revision: number };

function InvoicesSection() {
  const invoices = useQuery({ queryKey: ["invoices"], queryFn: () => apiFetch<{ items: Invoice[] }>("/api/v1/invoices") });
  const cards = useCards(); const accounts = useAccounts(); const queryClient = useQueryClient();
  const refresh = () => { void queryClient.invalidateQueries({ queryKey: ["invoices"] }); void queryClient.invalidateQueries({ queryKey: ["accounts"] }); void queryClient.invalidateQueries({ queryKey: ["cards"] }); void queryClient.invalidateQueries({ queryKey: ["future-balance"] }); };
  const transition = useMutation({ mutationFn: ({ invoice, action }: { invoice: Invoice; action: "close" | "reopen" }) => apiFetch(`/api/v1/invoices/${invoice.id}/${action}`, { method: "POST", body: JSON.stringify({ expected_revision: invoice.revision, reason: action === "reopen" ? "Reabertura solicitada pelo usuário" : null }) }), onSuccess: refresh });
  const plan = useMutation({ mutationFn: (invoice: Invoice) => { const card = cards.data?.items.find(item => item.id === invoice.card_id); if (!card?.default_account_id) throw new Error("Cartão sem conta padrão"); return apiFetch(`/api/v1/invoices/${invoice.id}/payment-plan`, { method: "PUT", body: JSON.stringify({ account_id: card.default_account_id, planned_date: invoice.due_date }) }); }, onSuccess: refresh });
  const pay = useMutation({ mutationFn: async (invoice: Invoice) => { const card = cards.data?.items.find(item => item.id === invoice.card_id); const accountId = card?.default_account_id; if (!accountId) throw new Error("Cartão sem conta padrão"); const preview = await apiFetch<{ preview_token: string; amount_minor: number }>(`/api/v1/invoices/${invoice.id}/payment-preview?account_id=${accountId}&paid_date=${todayIso()}`); return apiFetch(`/api/v1/invoices/${invoice.id}/payments`, { method: "POST", headers: idempotencyHeaders(), body: JSON.stringify({ account_id: accountId, paid_date: todayIso(), amount_minor: preview.amount_minor, preview_token: preview.preview_token }) }); }, onSuccess: refresh });
  const items = invoices.data?.items ?? [];
  return <section className="panel wide"><div className="panel-heading"><div><h2>Faturas</h2><p>Fechamento, planejamento e pagamento integral.</p></div></div>{items.length ? <div className="movement-list">{items.map(invoice => { const card = cards.data?.items.find(item => item.id === invoice.card_id); const account = accounts.data?.items.find(item => item.id === card?.default_account_id); return <article className="movement-row" key={invoice.id}><strong>{card?.name ?? "Cartão"} · {invoice.reference_month}</strong><span>{invoice.state === "open" ? "Aberta" : invoice.state === "closed" ? "Fechada" : "Paga"}</span><span>{account?.name ?? "Sem conta padrão"}</span><time>{invoice.due_date}</time><span>{formatBrl(invoice.payable_minor)}</span><span className="movement-action">{invoice.state === "open" && <button className="secondary" onClick={() => transition.mutate({ invoice, action: "close" })}>Fechar</button>}{invoice.state === "closed" && <><button className="secondary" onClick={() => plan.mutate(invoice)}>Planejar</button><button className="primary" onClick={() => pay.mutate(invoice)}>Pagar</button><button className="ghost" onClick={() => transition.mutate({ invoice, action: "reopen" })}>Reabrir</button></>}</span></article>; })}</div> : <div className="empty">Nenhuma fatura gerada.</div>}</section>;
}

function CardsSection() {
  const cards = useCards();
  const accounts = useAccounts();
  const queryClient = useQueryClient();
  const [registeringCard, setRegisteringCard] = useState(false);
  const [editingCard, setEditingCard] = useState<Card | null>(null);
  const form = useForm<CardFormValues, unknown, z.output<typeof cardSchema>>({ resolver: zodResolver(cardSchema), defaultValues: emptyCard });

  useEffect(() => {
    if (!editingCard) {
      form.reset(emptyCard);
      return;
    }
    form.reset({
      name: editingCard.name,
      accountId: editingCard.default_account_id ?? "",
      spent: (editingCard.limit_minor / 100).toFixed(2).replace(".", ","),
      closingDay: String(editingCard.closing_day),
      dueDay: String(editingCard.due_day),
    });
  }, [editingCard, form]);

  const saveCard = useMutation({
    mutationFn: (values: z.output<typeof cardSchema>) => editingCard
      ? apiFetch(`/api/v1/cards/${editingCard.id}`, {
          method: "PUT",
          body: JSON.stringify({ name: values.name, default_account_id: values.accountId, limit_minor: values.spent, expected_revision: editingCard.revision }),
        })
      : apiFetch("/api/v1/cards", {
          method: "POST",
          body: JSON.stringify({ name: values.name, default_account_id: values.accountId, limit_minor: values.spent, closing_day: values.closingDay, due_day: values.dueDay }),
        }),
    onSuccess: () => {
      setEditingCard(null);
      setRegisteringCard(false);
      form.reset(emptyCard);
      void queryClient.invalidateQueries({ queryKey: ["cards"] });
    },
  });

  const bankName = (card: Card) => {
    const account = accounts.data?.items.find((item) => item.id === card.default_account_id);
    return account?.institution || account?.name || "Banco não informado";
  };
  const cardItems = cards.data?.items ?? [];
  const totalLimit = cardItems.reduce((sum, card) => sum + card.limit_minor, 0);
  const totalCommitment = cardItems.reduce((sum, card) => sum + card.commitment_minor, 0);

  return <>
    <section className="panel wide investments-panel cards-panel">
      <div className="panel-heading investment-portfolio-heading accounts-section-heading">
        <div><h2>Seus cartões</h2><p>{cardItems.length} {cardItems.length === 1 ? "cartão cadastrado" : "cartões cadastrados"}</p></div>
        <div className="accounts-heading-actions">
          <div className="investment-portfolio-total"><span>Limite comprometido</span><strong>{formatBrl(totalCommitment)}</strong></div>
          <div className="investment-portfolio-total"><span>Limite total</span><strong>{formatBrl(totalLimit)}</strong></div>
          <button className="primary overview-new-transaction" type="button" onClick={() => setRegisteringCard(true)}><span aria-hidden="true">＋</span> Novo cartão</button>
        </div>
      </div>
      <AsyncState loading={cards.isPending || accounts.isPending} error={cards.isError || accounts.isError} empty={!cards.data?.items.length}>
        <div className="account-cards investment-cards account-balance-cards">{cardItems.map((card) => <article key={card.id}>
          <div className="investment-card-heading"><h3>{card.name}</h3><button type="button" className="movement-edit-button" aria-label={`Editar cartão ${card.name}`} title="Editar cartão" onClick={() => setEditingCard(card)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button></div>
          <strong>{formatBrl(card.limit_minor)}</strong>
          <div className="account-card-meta"><span>{bankName(card)}</span><span>Fecha dia {card.closing_day} · Vence dia {card.due_day}</span></div>
        </article>)}</div>
      </AsyncState>
    </section>
    {(registeringCard || editingCard) && <div className="modal-backdrop"><form className="modal form-panel investment-modal transaction-modal" role="dialog" aria-modal="true" aria-labelledby="card-form-title" onSubmit={form.handleSubmit((values) => saveCard.mutate(values))}>
        <h2 id="card-form-title">{editingCard ? "Editar cartão" : "Novo cartão"}</h2>
        <label className="field"><span>Nome do cartão</span><input {...form.register("name")} />{form.formState.errors.name && <small className="field-error">{form.formState.errors.name.message}</small>}</label>
        <label className="field"><span>Banco</span><select {...form.register("accountId")}><option value="">Selecione um banco</option>{accounts.data?.items.map((account) => <option key={account.id} value={account.id}>{account.institution || account.name}</option>)}</select>{form.formState.errors.accountId && <small className="field-error">Selecione um banco.</small>}</label>
        <MoneyField label="Limite do cartão" registration={form.register("spent")} error={form.formState.errors.spent} />
        {!editingCard && <><label className="field"><span>Dia de fechamento</span><input type="number" min="1" max="31" {...form.register("closingDay")} /></label><label className="field"><span>Dia de vencimento</span><input type="number" min="1" max="31" {...form.register("dueDay")} /></label></>}
        {saveCard.isError && <p className="field-error" role="alert">Não foi possível salvar o cartão.</p>}
        <div className="modal-actions"><button type="button" className="ghost overview-new-transaction" onClick={() => { setEditingCard(null); setRegisteringCard(false); }}>Cancelar</button><button className="primary overview-new-transaction" disabled={saveCard.isPending}>{editingCard ? "Salvar alterações" : "Salvar"}</button></div>
      </form></div>}
  </>;
}

export function AccountsPage() {
  const accounts = useAccounts();
  const queryClient = useQueryClient();
  const [registeringAccount, setRegisteringAccount] = useState(false);
  const [editing, setEditing] = useState<Account | null>(null);
  const [editName, setEditName] = useState("");
  const accountForm = useForm<z.input<typeof accountSchema>>({ resolver: zodResolver(accountSchema), defaultValues: { name: "", institution: "", balance: "0,00", referenceDate: todayIso() } });
  const refresh = () => { void queryClient.invalidateQueries({ queryKey: ["accounts"] }); void queryClient.invalidateQueries({ queryKey: ["monthly"] }); };
  const add = useMutation({ mutationFn: (v: z.output<typeof accountSchema>) => apiFetch("/api/v1/accounts", { method: "POST", body: JSON.stringify({ name: v.name, institution: v.institution || null, reference_balance_minor: v.balance, reference_date: v.referenceDate }) }), onSuccess: () => { accountForm.reset(); setRegisteringAccount(false); refresh(); } });
  const rename = useMutation({ mutationFn: (account: Account) => apiFetch(`/api/v1/accounts/${account.id}`, { method: "PUT", body: JSON.stringify({ name: editName, institution: account.institution, expected_revision: account.revision }) }), onSuccess: () => { setEditing(null); refresh(); } });
  const archive = useMutation({ mutationFn: (account: Account) => apiFetch(`/api/v1/accounts/${account.id}/archive`, { method: "POST", body: JSON.stringify({ expected_revision: account.revision, reason: "Arquivada pelo usuário" }) }), onSuccess: refresh });
  const accountItems = accounts.data?.items ?? [];
  const totalBalance = accountItems.reduce((sum, account) => sum + account.current_balance_minor, 0);
  return <Page title="Contas e cartões" description="Acompanhe seus saldos, limites e instituições financeiras em um só lugar." actions={<button className="primary overview-new-transaction investment-page-action" type="button" onClick={() => setRegisteringAccount(true)}><span aria-hidden="true">＋</span> Nova conta</button>}>
    <div className="account-grid"><section className="panel wide investments-panel"><div className="panel-heading investment-portfolio-heading"><div><h2>Suas contas</h2><p>{accountItems.length} {accountItems.length === 1 ? "conta ativa" : "contas ativas"}</p></div><div className="investment-portfolio-total"><span>Saldo total</span><strong>{formatBrl(totalBalance)}</strong></div></div><AsyncState loading={accounts.isPending} error={accounts.isError} empty={accounts.data?.total === 0}><div className="account-cards investment-cards account-balance-cards">{accountItems.map((account) => <article key={account.id}><div className="investment-card-heading"><h3>{account.institution || account.name}</h3><button type="button" className="movement-edit-button" aria-label={`Editar conta ${account.name}`} title="Editar conta" onClick={() => { setEditing(account); setEditName(account.name); }}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button></div><strong>{formatBrl(account.current_balance_minor)}</strong><div className="account-card-meta"><span>Saldo atual</span>{account.institution && account.name !== account.institution && <span>{account.name}</span>}</div></article>)}</div></AsyncState></section>
    </div>
    <CardsSection />
    <InvoicesSection />
    {registeringAccount && <div className="modal-backdrop"><form className="modal form-panel investment-modal transaction-modal" role="dialog" aria-modal="true" aria-labelledby="new-account-title" onSubmit={accountForm.handleSubmit((v) => add.mutate(accountSchema.parse(v)))}><h2 id="new-account-title">Nova conta</h2><label className="field"><span>Nome</span><input {...accountForm.register("name")} /></label><label className="field"><span>Instituição</span><input {...accountForm.register("institution")} /></label><MoneyField label="Saldo inicial da data" registration={accountForm.register("balance")} error={accountForm.formState.errors.balance} /><label className="field"><span>Data de referência</span><input type="date" {...accountForm.register("referenceDate")} /></label><div className="modal-actions"><button type="button" className="ghost overview-new-transaction" onClick={() => setRegisteringAccount(false)}>Cancelar</button><button className="primary overview-new-transaction" disabled={add.isPending}>{add.isPending ? "Salvando…" : "Salvar"}</button></div></form></div>}
    {editing && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true"><h2>Editar conta</h2><label className="field"><span>Nome</span><input value={editName} onChange={(event) => setEditName(event.target.value)} /></label><div className="modal-actions"><button className="danger" onClick={() => { if (window.confirm(`Arquivar ${editing.name}? O histórico e as obrigações continuarão visíveis.`)) { archive.mutate(editing); setEditing(null); } }}>Arquivar</button><button className="ghost" onClick={() => setEditing(null)}>Cancelar</button><button className="primary" disabled={!editName.trim()} onClick={() => rename.mutate(editing)}>Salvar</button></div></section></div>}
  </Page>;
}
