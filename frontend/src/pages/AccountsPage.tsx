import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { apiFetch } from "../api/client";
import type { Account, Card } from "../api/types";
import { AsyncState } from "../components/AsyncState";
import { MoneyField } from "../components/MoneyField";
import { Page } from "../components/Page";
import { useAccounts, useCards } from "../hooks/useFinanceData";
import { moneyText, requiredText, todayIso } from "../lib/forms";
import { formatBrl } from "../lib/money";

const accountSchema = z.object({ name: requiredText, institution: z.string(), balance: moneyText, referenceDate: z.string() });
const cardSchema = z.object({ name: requiredText, accountId: requiredText, spent: moneyText });
type CardFormValues = z.input<typeof cardSchema>;
const emptyCard: CardFormValues = { name: "", accountId: "", spent: "" };

function CardsSection() {
  const cards = useCards();
  const accounts = useAccounts();
  const queryClient = useQueryClient();
  const [registeringCard, setRegisteringCard] = useState(false);
  const [editingCard, setEditingCard] = useState<Card | null>(null);
  const form = useForm<CardFormValues>({ resolver: zodResolver(cardSchema), defaultValues: emptyCard });

  useEffect(() => {
    if (!editingCard) {
      form.reset(emptyCard);
      return;
    }
    form.reset({
      name: editingCard.name,
      accountId: editingCard.default_account_id ?? "",
      spent: (editingCard.limit_minor / 100).toFixed(2).replace(".", ","),
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
          body: JSON.stringify({ name: values.name, default_account_id: values.accountId, limit_minor: values.spent, closing_day: 1, due_day: 1 }),
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

  return <>
    <section className="panel wide investments-panel cards-panel">
      <div className="panel-heading"><h2>Cartões</h2></div>
      <AsyncState loading={cards.isPending || accounts.isPending} error={cards.isError || accounts.isError} empty={!cards.data?.items.length}>
        <div className="account-cards investment-cards account-balance-cards">{cards.data?.items.map((card) => <article key={card.id}>
          <strong>{formatBrl(card.limit_minor)}</strong><h3>{card.name} · {bankName(card)}</h3><button type="button" className="movement-edit-button" aria-label={`Editar cartão ${card.name}`} title="Editar cartão" onClick={() => setEditingCard(card)}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button>
        </article>)}</div>
      </AsyncState>
      <div className="investment-panel-action"><button className="primary overview-new-transaction" type="button" onClick={() => setRegisteringCard(true)}><span aria-hidden="true">＋</span> Novo Cartão</button></div>
    </section>
    {(registeringCard || editingCard) && <div className="modal-backdrop"><form className="modal form-panel investment-modal transaction-modal" role="dialog" aria-modal="true" aria-labelledby="card-form-title" onSubmit={form.handleSubmit((values) => saveCard.mutate(cardSchema.parse(values)))}>
        <h2 id="card-form-title">{editingCard ? "Editar cartão" : "Novo cartão"}</h2>
        <label className="field"><span>Nome do cartão</span><input {...form.register("name")} />{form.formState.errors.name && <small className="field-error">{form.formState.errors.name.message}</small>}</label>
        <label className="field"><span>Banco</span><select {...form.register("accountId")}><option value="">Selecione um banco</option>{accounts.data?.items.map((account) => <option key={account.id} value={account.id}>{account.institution || account.name}</option>)}</select>{form.formState.errors.accountId && <small className="field-error">Selecione um banco.</small>}</label>
        <MoneyField label="Valor gasto" registration={form.register("spent")} error={form.formState.errors.spent} />
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
  return <Page title="Contas e cartões">
    <div className="account-grid"><section className="panel wide investments-panel"><div className="panel-heading"><h2>Contas</h2></div><AsyncState loading={accounts.isPending} error={accounts.isError} empty={accounts.data?.total === 0}><div className="account-cards investment-cards account-balance-cards">{accounts.data?.items.map((account) => <article key={account.id}><strong>{formatBrl(account.current_balance_minor)}</strong><h3>{account.institution || account.name}</h3><button type="button" className="movement-edit-button" aria-label={`Editar conta ${account.name}`} title="Editar conta" onClick={() => { setEditing(account); setEditName(account.name); }}><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 20h9"/><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"/></svg></button></article>)}</div></AsyncState><div className="investment-panel-action"><button className="primary overview-new-transaction" type="button" onClick={() => setRegisteringAccount(true)}><span aria-hidden="true">＋</span> Nova Conta</button></div></section>
    </div>
    <CardsSection />
    {registeringAccount && <div className="modal-backdrop"><form className="modal form-panel investment-modal transaction-modal" role="dialog" aria-modal="true" aria-labelledby="new-account-title" onSubmit={accountForm.handleSubmit((v) => add.mutate(accountSchema.parse(v)))}><h2 id="new-account-title">Nova conta</h2><label className="field"><span>Nome</span><input {...accountForm.register("name")} /></label><label className="field"><span>Instituição</span><input {...accountForm.register("institution")} /></label><MoneyField label="Saldo inicial da data" registration={accountForm.register("balance")} error={accountForm.formState.errors.balance} /><label className="field"><span>Data de referência</span><input type="date" {...accountForm.register("referenceDate")} /></label><div className="modal-actions"><button type="button" className="ghost overview-new-transaction" onClick={() => setRegisteringAccount(false)}>Cancelar</button><button className="primary overview-new-transaction" disabled={add.isPending}>{add.isPending ? "Salvando…" : "Salvar"}</button></div></form></div>}
    {editing && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true"><h2>Editar conta</h2><label className="field"><span>Nome</span><input value={editName} onChange={(event) => setEditName(event.target.value)} /></label><div className="modal-actions"><button className="danger" onClick={() => { if (window.confirm(`Arquivar ${editing.name}? O histórico e as obrigações continuarão visíveis.`)) { archive.mutate(editing); setEditing(null); } }}>Arquivar</button><button className="ghost" onClick={() => setEditing(null)}>Cancelar</button><button className="primary" disabled={!editName.trim()} onClick={() => rename.mutate(editing)}>Salvar</button></div></section></div>}
  </Page>;
}
