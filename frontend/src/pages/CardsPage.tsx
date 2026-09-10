import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ApiError, apiFetch, idempotencyHeaders } from "../api/client";
import type { Card, Installment, Invoice, Page as PageType, Purchase } from "../api/types";
import { AsyncState } from "../components/AsyncState";
import { MoneyField } from "../components/MoneyField";
import { Page } from "../components/Page";
import { useAccounts, useCards, useCategories, useInvoices } from "../hooks/useFinanceData";
import { currentMonth, moneyText, requiredText, todayIso } from "../lib/forms";
import { formatBrl } from "../lib/money";
import { formatDateBr, formatMonthBr } from "../lib/dates";

const cardSchema = z.object({
  name: requiredText,
  limit: moneyText,
  closingDay: z.coerce.number().int().min(1).max(31),
  dueDay: z.coerce.number().int().min(1).max(31),
  accountId: z.string(),
});
const purchaseSchema = z.object({
  cardId: requiredText,
  categoryId: z.string(),
  description: requiredText,
  purchaseDate: z.string(),
  total: moneyText,
  count: z.coerce.number().int().min(1),
  firstMonth: z.string(),
});
const openingSchema = z.object({ cardId: requiredText, categoryId: z.string(), description: requiredText, purchaseDate: z.string(), total: moneyText, totalInstallments: z.coerce.number().int().min(1), nextInstallment: z.coerce.number().int().min(1), firstMonth: z.string() });
const aggregateSchema = z.object({ invoiceId: requiredText, description: requiredText, amount: moneyText });
const refundSchema = z.object({ purchaseId: requiredText, amount: moneyText, status: z.enum(["planned", "confirmed"]), plannedDate: z.string(), recognitionDate: z.string(), targetKind: z.enum(["invoice", "account"]), targetId: requiredText, reason: requiredText });
type PurchasePreview = {
  preview_token: string;
  total_minor: number;
  estimated_commitment_after_minor: number;
  schedule: { installment_number: number; amount_minor: number; reference_month: string; due_date: string }[];
};
type PaymentPreview = {
  preview_token: string; invoice_id: string; account_id: string; paid_date: string;
  amount_minor: number; resulting_balance_minor: number; insufficient_balance: boolean;
};
type RefundPreview = { preview_token: string; amount_minor: number; remaining_eligible_minor: number; analytical_effect: string };
type InvoiceDetail = { invoice: Invoice; installments: Installment[]; adjustments: { id: string; description: string; signed_amount_minor: number; kind: string; status: string }[] };
type CancelPreview = { preview_token: string; amount_minor: number; invoice_month: string; remaining_eligible_minor: number };

export function CardsPage() {
  const cards = useCards();
  const accounts = useAccounts();
  const categories = useCategories();
  const invoices = useInvoices();
  const purchases = useQuery({ queryKey: ["purchases"], queryFn: () => apiFetch<PageType<Purchase>>("/api/v1/purchases?page_size=100") });
  const queryClient = useQueryClient();
  const [preview, setPreview] = useState<{ input: z.output<typeof purchaseSchema>; result: PurchasePreview } | null>(null);
  const [payment, setPayment] = useState<PaymentPreview | null>(null);
  const [paymentNotice, setPaymentNotice] = useState("");
  const [selectedInvoice, setSelectedInvoice] = useState<string | null>(null);
  const invoiceDetail = useQuery({ queryKey: ["invoice-detail", selectedInvoice], queryFn: () => apiFetch<InvoiceDetail>(`/api/v1/invoices/${selectedInvoice}`), enabled: !!selectedInvoice });
  const [refundPreview, setRefundPreview] = useState<{ input: z.output<typeof refundSchema>; result: RefundPreview } | null>(null);
  const [cancelPreview, setCancelPreview] = useState<{ item: Installment; result: CancelPreview } | null>(null);
  const [editingCard, setEditingCard] = useState<Card | null>(null);
  const [closingDay, setClosingDay] = useState(10);
  const [dueDay, setDueDay] = useState(20);
  const [replacementAdjustment, setReplacementAdjustment] = useState<string | null>(null);
  const [replacementIds, setReplacementIds] = useState<string[]>([]);
  const [replacementAmount, setReplacementAmount] = useState("");
  const cardForm = useForm<z.input<typeof cardSchema>>({
    resolver: zodResolver(cardSchema),
    defaultValues: { name: "", limit: "", closingDay: 10, dueDay: 20, accountId: "" },
  });
  const purchaseForm = useForm<z.input<typeof purchaseSchema>>({
    resolver: zodResolver(purchaseSchema),
    defaultValues: { cardId: "", categoryId: "", description: "", purchaseDate: todayIso(), total: "", count: 1, firstMonth: currentMonth() },
  });
  const openingForm = useForm<z.input<typeof openingSchema>>({ resolver: zodResolver(openingSchema), defaultValues: { cardId: "", categoryId: "", description: "", purchaseDate: todayIso(), total: "", totalInstallments: 1, nextInstallment: 1, firstMonth: currentMonth() } });
  const aggregateForm = useForm<z.input<typeof aggregateSchema>>({ resolver: zodResolver(aggregateSchema), defaultValues: { invoiceId: "", description: "Compromisso inicial sem detalhamento", amount: "" } });
  const refundForm = useForm<z.input<typeof refundSchema>>({ resolver: zodResolver(refundSchema), defaultValues: { purchaseId: "", amount: "", status: "confirmed", plannedDate: todayIso(), recognitionDate: todayIso(), targetKind: "invoice", targetId: "", reason: "" } });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["cards"] });
    void queryClient.invalidateQueries({ queryKey: ["invoices"] });
    void queryClient.invalidateQueries({ queryKey: ["accounts"] });
    void queryClient.invalidateQueries({ queryKey: ["monthly"] });
    void queryClient.invalidateQueries({ queryKey: ["purchases"] });
    void queryClient.invalidateQueries({ queryKey: ["invoice-detail"] });
  };
  const addCard = useMutation({
    mutationFn: (value: z.output<typeof cardSchema>) => apiFetch("/api/v1/cards", {
      method: "POST",
      body: JSON.stringify({ name: value.name, limit_minor: value.limit, closing_day: value.closingDay, due_day: value.dueDay, default_account_id: value.accountId || null }),
    }),
    onSuccess: () => { cardForm.reset(); refresh(); },
  });
  const requestPreview = useMutation({
    mutationFn: async (value: z.output<typeof purchaseSchema>) => ({
      input: value,
      result: await apiFetch<PurchasePreview>("/api/v1/purchases/preview", {
        method: "POST",
        body: JSON.stringify({ card_id: value.cardId, category_id: value.categoryId || null, description: value.description, purchase_date: value.purchaseDate, total_minor: value.total, installment_count: value.count, first_invoice_month: value.firstMonth }),
      }),
    }),
    onSuccess: setPreview,
  });
  const confirm = useMutation({
    mutationFn: ({ input, result }: NonNullable<typeof preview>) => apiFetch("/api/v1/purchases", {
      method: "POST",
      headers: idempotencyHeaders(),
      body: JSON.stringify({ card_id: input.cardId, category_id: input.categoryId || null, description: input.description, purchase_date: input.purchaseDate, total_minor: input.total, installment_count: input.count, first_invoice_month: input.firstMonth, preview_token: result.preview_token }),
    }),
    onSuccess: () => { setPreview(null); purchaseForm.reset(); refresh(); },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "STALE_PREVIEW" && error.detail?.preview) {
        setPreview((current) => current ? { input: current.input, result: error.detail?.preview as PurchasePreview } : null);
      }
    },
  });
  const close = useMutation({
    mutationFn: (invoice: Invoice) => apiFetch(`/api/v1/invoices/${invoice.id}/close`, { method: "POST", body: JSON.stringify({ expected_revision: invoice.revision }) }),
    onSuccess: refresh,
  });
  const requestPayment = useMutation({
    mutationFn: (invoice: Invoice) => {
      const accountId = cards.data?.items.find((card) => card.id === invoice.card_id)?.default_account_id;
      if (!accountId) throw new Error("Defina uma conta habitual ou um plano de pagamento.");
      return apiFetch<PaymentPreview>(`/api/v1/invoices/${invoice.id}/payment-preview?account_id=${encodeURIComponent(accountId)}&paid_date=${todayIso()}`);
    },
    onSuccess: (result) => { setPaymentNotice(""); setPayment(result); },
    onError: (error) => setPaymentNotice(error instanceof Error ? error.message : "Não foi possível preparar o pagamento."),
  });
  const pay = useMutation({
    mutationFn: (value: PaymentPreview) => apiFetch(`/api/v1/invoices/${value.invoice_id}/payments`, {
      method: "POST",
      headers: idempotencyHeaders(),
      body: JSON.stringify({ account_id: value.account_id, paid_date: value.paid_date, amount_minor: value.amount_minor, preview_token: value.preview_token }),
    }),
    onSuccess: () => { setPayment(null); refresh(); },
    onError: (error) => {
      if (error instanceof ApiError && error.code === "STALE_PREVIEW" && error.detail?.preview) {
        setPayment(error.detail.preview as PaymentPreview);
        setPaymentNotice("A fatura mudou. Confira a nova prévia antes de confirmar novamente.");
      } else setPaymentNotice(error instanceof Error ? error.message : "Pagamento não concluído.");
    },
  });
  const addOpening = useMutation({ mutationFn: (value: z.output<typeof openingSchema>) => apiFetch(`/api/v1/cards/${value.cardId}/opening-purchases`, { method: "POST", body: JSON.stringify({ description: value.description, purchase_date: value.purchaseDate, total_minor: value.total, total_installments: value.totalInstallments, next_installment: value.nextInstallment, category_id: value.categoryId || null, first_pending_invoice_month: value.firstMonth }) }), onSuccess: () => { openingForm.reset(); refresh(); } });
  const addAggregate = useMutation({ mutationFn: (value: z.output<typeof aggregateSchema>) => apiFetch(`/api/v1/invoices/${value.invoiceId}/adjustments`, { method: "POST", body: JSON.stringify({ signed_amount_minor: value.amount, kind: "opening", description: value.description, category_id: null }) }), onSuccess: () => { aggregateForm.reset(); refresh(); } });
  const requestRefund = useMutation({ mutationFn: async (input: z.output<typeof refundSchema>) => ({ input, result: await apiFetch<RefundPreview>("/api/v1/refunds/preview", { method: "POST", body: JSON.stringify({ purchase_id: input.purchaseId, amount_minor: input.amount, status: input.status, planned_date: input.plannedDate, recognition_date: input.status === "confirmed" ? input.recognitionDate : null, target_kind: input.targetKind, target_id: input.targetId, reason: input.reason }) }) }), onSuccess: setRefundPreview });
  const confirmRefund = useMutation({ mutationFn: ({ input, result }: NonNullable<typeof refundPreview>) => apiFetch("/api/v1/refunds/confirm", { method: "POST", headers: idempotencyHeaders(), body: JSON.stringify({ purchase_id: input.purchaseId, amount_minor: input.amount, status: input.status, planned_date: input.plannedDate, recognition_date: input.status === "confirmed" ? input.recognitionDate : null, target_kind: input.targetKind, target_id: input.targetId, reason: input.reason, preview_token: result.preview_token }) }), onSuccess: () => { setRefundPreview(null); refundForm.reset(); refresh(); }, onError: (error) => { if (error instanceof ApiError && error.code === "STALE_PREVIEW" && error.detail?.preview) setRefundPreview((current) => current ? { input: current.input, result: error.detail?.preview as RefundPreview } : null); } });
  const requestCancel = useMutation({ mutationFn: async (item: Installment) => ({ item, result: await apiFetch<CancelPreview>(`/api/v1/installments/${item.id}/cancel-preview`, { method: "POST", body: JSON.stringify({ expected_revision: item.revision, cancellation_date: todayIso(), reason: "Obrigação cancelada pelo emissor" }) }) }), onSuccess: setCancelPreview });
  const confirmCancel = useMutation({ mutationFn: ({ item, result }: NonNullable<typeof cancelPreview>) => apiFetch(`/api/v1/installments/${item.id}/cancel-confirm`, { method: "POST", body: JSON.stringify({ expected_revision: item.revision, cancellation_date: todayIso(), reason: "Obrigação cancelada pelo emissor", preview_token: result.preview_token }) }), onSuccess: () => { setCancelPreview(null); refresh(); }, onError: (error) => { if (error instanceof ApiError && error.code === "STALE_PREVIEW" && error.detail?.preview) setCancelPreview((current) => current ? { item: current.item, result: error.detail?.preview as CancelPreview } : null); } });
  const updateTerms = useMutation({ mutationFn: (card: Card) => apiFetch(`/api/v1/cards/${card.id}/terms`, { method: "POST", body: JSON.stringify({ closing_day: closingDay, due_day: dueDay, expected_revision: card.revision }) }), onSuccess: () => { setEditingCard(null); refresh(); } });
  const archiveCard = useMutation({ mutationFn: (card: Card) => apiFetch(`/api/v1/cards/${card.id}/archive`, { method: "POST", body: JSON.stringify({ expected_revision: card.revision, reason: "Arquivado pelo usuário" }) }), onSuccess: refresh });
  const replaceOpening = useMutation({ mutationFn: () => apiFetch(`/api/v1/invoice-adjustments/${replacementAdjustment}/replace-opening`, { method: "POST", body: JSON.stringify({ installment_ids: replacementIds, amount_minor: Number(replacementAmount) }) }), onSuccess: () => { setReplacementAdjustment(null); setReplacementIds([]); setReplacementAmount(""); refresh(); } });

  return (
    <Page eyebrow="Competência pela fatura" title="Cartões e faturas" description="A compra não reduz o saldo bancário; cada parcela entra no mês de vencimento.">
      <section className="card-strip">
        <AsyncState loading={cards.isPending} error={cards.isError} empty={!cards.data?.items.length}>
          {cards.data?.items.map((card) => <article className="credit-card" key={card.id}><small>Disponível estimado</small><strong>{formatBrl(card.available_estimated_minor)}</strong><h3>{card.name}</h3><p>{formatBrl(card.commitment_minor)} comprometidos de {formatBrl(card.limit_minor)}</p><div className="button-row"><button className="text-button light" onClick={() => { setEditingCard(card); setClosingDay(card.closing_day); setDueDay(card.due_day); }}>Alterar datas futuras</button><button className="text-button light" onClick={() => { if (window.confirm(`Arquivar ${card.name}? Faturas e histórico existentes continuarão visíveis.`)) archiveCard.mutate(card); }}>Arquivar</button></div></article>)}
        </AsyncState>
      </section>
      <div className="grid-form">
        <form className="panel form-panel" onSubmit={purchaseForm.handleSubmit((value) => requestPreview.mutate(purchaseSchema.parse(value)))}>
          <h2>Registrar compra</h2>
          <label className="field"><span>Cartão</span><select {...purchaseForm.register("cardId")}><option value="">Selecione</option>{cards.data?.items.map((card) => <option key={card.id} value={card.id}>{card.name}</option>)}</select></label>
          <label className="field"><span>Descrição</span><input {...purchaseForm.register("description")} /></label>
          <label className="field"><span>Categoria</span><select {...purchaseForm.register("categoryId")}><option value="">Sem categoria</option>{categories.data?.items.filter((item) => item.kind === "expense").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <MoneyField label="Valor total" registration={purchaseForm.register("total")} error={purchaseForm.formState.errors.total} />
          <div className="field-row"><label className="field"><span>Parcelas</span><input type="number" min="1" {...purchaseForm.register("count")} /></label><label className="field"><span>Data da compra</span><input type="date" {...purchaseForm.register("purchaseDate")} /></label></div>
          <label className="field"><span>Primeira fatura</span><input type="month" {...purchaseForm.register("firstMonth")} /></label>
          <button className="primary">Ver cronograma</button>
        </form>
        <section className="panel">
          <div className="panel-heading"><h2>Faturas</h2><span>Pagamentos são caixa</span></div>
          {paymentNotice && <p className="field-error" role="alert">{paymentNotice}</p>}
          <AsyncState loading={invoices.isPending} error={invoices.isError} empty={!invoices.data?.items.length}>
            <div className="list">{invoices.data?.items.map((invoice) => <article className="list-row" key={invoice.id}><div><strong>{formatMonthBr(invoice.reference_month)}</strong><small>Vence {formatDateBr(invoice.due_date)} · {invoice.state}</small></div><div className="invoice-action"><span>{formatBrl(invoice.payable_minor)}</span><button className="text-button" onClick={() => setSelectedInvoice(invoice.id)}>Ver origem</button>{invoice.state === "open" && <button className="text-button" onClick={() => close.mutate(invoice)}>Fechar</button>}{invoice.state === "closed" && <button className="text-button" onClick={() => requestPayment.mutate(invoice)}>Pagar integral</button>}</div></article>)}</div>
          </AsyncState>
        </section>
      </div>
      {preview && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="purchase-preview-title"><p className="eyebrow">Prévia obrigatória</p><h2 id="purchase-preview-title">Cronograma da compra</h2><p>Total {formatBrl(preview.result.total_minor)} · comprometimento estimado após a compra {formatBrl(preview.result.estimated_commitment_after_minor)}</p><table><thead><tr><th>Parcela</th><th>Fatura</th><th>Vencimento</th><th>Valor</th></tr></thead><tbody>{preview.result.schedule.map((item) => <tr key={item.installment_number}><td>{item.installment_number}</td><td>{formatMonthBr(item.reference_month)}</td><td>{formatDateBr(item.due_date)}</td><td>{formatBrl(item.amount_minor)}</td></tr>)}</tbody></table>{confirm.isError && <p className="field-error" role="alert">A prévia foi atualizada ou a compra não pôde ser salva.</p>}<div className="modal-actions"><button className="ghost" onClick={() => setPreview(null)}>Voltar</button><button className="primary" disabled={confirm.isPending} onClick={() => confirm.mutate(preview)}>Confirmar compra</button></div></section></div>}
      {payment && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true" aria-labelledby="payment-title"><p className="eyebrow">Prévia obrigatória</p><h2 id="payment-title">Pagamento integral</h2><p>Saída da conta: <strong>{formatBrl(payment.amount_minor)}</strong></p><p>Saldo resultante: {formatBrl(payment.resulting_balance_minor)}</p>{payment.insufficient_balance && <p className="alert-text">Saldo insuficiente: a confirmação é permitida e deixará a conta negativa.</p>}{paymentNotice && <p className="field-error" role="alert">{paymentNotice}</p>}<div className="modal-actions"><button className="ghost" onClick={() => setPayment(null)}>Voltar</button><button className="primary" onClick={() => pay.mutate(payment)}>Confirmar pagamento</button></div></section></div>}
      <details className="panel compact"><summary>Cadastrar cartão</summary><form className="inline-form" onSubmit={cardForm.handleSubmit((value) => addCard.mutate(cardSchema.parse(value)))}><label className="field"><span>Nome</span><input {...cardForm.register("name")} /></label><MoneyField label="Limite estimado" registration={cardForm.register("limit")} error={cardForm.formState.errors.limit} /><label className="field"><span>Fechamento</span><input type="number" min="1" max="31" {...cardForm.register("closingDay")} /></label><label className="field"><span>Vencimento</span><input type="number" min="1" max="31" {...cardForm.register("dueDay")} /></label><label className="field"><span>Conta habitual</span><select {...cardForm.register("accountId")}><option value="">Sem conta definida</option>{accounts.data?.items.map((account) => <option value={account.id} key={account.id}>{account.name}</option>)}</select></label><button className="primary">Salvar cartão</button></form></details>
      <details className="panel compact"><summary>Informar compra antiga e parcelas restantes</summary><form className="inline-form" onSubmit={openingForm.handleSubmit((value) => addOpening.mutate(openingSchema.parse(value)))}><label className="field"><span>Cartão</span><select {...openingForm.register("cardId")}><option value="">Selecione</option>{cards.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>Descrição</span><input {...openingForm.register("description")} /></label><MoneyField label="Valor total original" registration={openingForm.register("total")} error={openingForm.formState.errors.total} /><label className="field"><span>Categoria</span><select {...openingForm.register("categoryId")}><option value="">Sem categoria</option>{categories.data?.items.filter((item) => item.kind === "expense").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>Data original</span><input type="date" {...openingForm.register("purchaseDate")} /></label><label className="field"><span>Total de parcelas</span><input type="number" min="1" {...openingForm.register("totalInstallments")} /></label><label className="field"><span>Próxima parcela</span><input type="number" min="1" {...openingForm.register("nextInstallment")} /></label><label className="field"><span>Primeira fatura pendente</span><input type="month" {...openingForm.register("firstMonth")} /></label><p className="hint">Somente as parcelas restantes viram novas obrigações.</p><button className="primary">Registrar situação inicial</button></form></details>
      <details className="panel compact"><summary>Alternativa: compromisso inicial agregado</summary><form className="inline-form" onSubmit={aggregateForm.handleSubmit((value) => addAggregate.mutate(aggregateSchema.parse(value)))}><label className="field"><span>Fatura aberta</span><select {...aggregateForm.register("invoiceId")}><option value="">Selecione</option>{invoices.data?.items.filter((item) => item.state === "open").map((item) => <option key={item.id} value={item.id}>{formatMonthBr(item.reference_month)}</option>)}</select></label><label className="field"><span>Descrição</span><input {...aggregateForm.register("description")} /></label><MoneyField label="Contribuição nesta fatura" registration={aggregateForm.register("amount")} error={aggregateForm.formState.errors.amount} /><p className="hint">Sem categoria por padrão. Ao detalhar depois, substitua a contribuição em vez de somá-la novamente.</p><button className="primary">Registrar agregado</button></form></details>
      <details className="panel compact"><summary>Registrar estorno de compra</summary><form className="inline-form" onSubmit={refundForm.handleSubmit((value) => requestRefund.mutate(refundSchema.parse(value)))}><label className="field"><span>Compra original</span><select {...refundForm.register("purchaseId")}><option value="">Selecione</option>{purchases.data?.items.map((item) => <option key={item.id} value={item.id}>{item.description} · {formatBrl(item.total_minor)}</option>)}</select></label><MoneyField label="Valor do estorno" registration={refundForm.register("amount")} error={refundForm.formState.errors.amount} /><label className="field"><span>Estado</span><select {...refundForm.register("status")}><option value="confirmed">Crédito confirmado</option><option value="planned">Crédito previsto</option></select></label><label className="field"><span>Destino real</span><select {...refundForm.register("targetKind")}><option value="invoice">Fatura do mesmo cartão</option><option value="account">Reembolso em conta</option></select></label><label className="field"><span>Fatura ou conta</span><select {...refundForm.register("targetId")}><option value="">Selecione</option><optgroup label="Faturas não liquidadas">{invoices.data?.items.filter((item) => item.state !== "settled").map((item) => <option key={item.id} value={item.id}>{formatMonthBr(item.reference_month)}</option>)}</optgroup><optgroup label="Contas">{accounts.data?.items.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</optgroup></select></label><label className="field"><span>Data esperada</span><input type="date" {...refundForm.register("plannedDate")} /></label><label className="field"><span>Data reconhecida</span><input type="date" max={todayIso()} {...refundForm.register("recognitionDate")} /></label><label className="field"><span>Motivo</span><input {...refundForm.register("reason")} /></label><button className="primary">Revisar estorno</button></form></details>
      {selectedInvoice && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true"><h2>Origem da fatura</h2><AsyncState loading={invoiceDetail.isPending} error={invoiceDetail.isError}><table><thead><tr><th>Item</th><th>Estado</th><th>Valor</th><th>Ação</th></tr></thead><tbody>{invoiceDetail.data?.installments.map((item) => <tr key={item.id}><td><label><input type="checkbox" checked={replacementIds.includes(item.id)} onChange={(event) => setReplacementIds((current) => event.target.checked ? [...current, item.id] : current.filter((id) => id !== item.id))} /> Parcela {item.installment_number}</label></td><td>{item.status}</td><td>{formatBrl(item.amount_minor)}</td><td>{item.status === "confirmed" && invoiceDetail.data?.invoice.state !== "settled" ? <button className="text-button" onClick={() => requestCancel.mutate(item)}>Revisar cancelamento</button> : "—"}</td></tr>)}{invoiceDetail.data?.adjustments.map((item) => <tr key={item.id}><td>{item.description}</td><td>{item.kind}</td><td>{formatBrl(item.signed_amount_minor)}</td><td>{item.kind === "opening" && item.status === "active" ? <button className="text-button" onClick={() => { setReplacementAdjustment(item.id); setReplacementAmount(String(item.signed_amount_minor)); }}>Substituir contribuição</button> : "Vínculo preservado"}</td></tr>)}</tbody></table>{replacementAdjustment && <div className="preview"><p>Selecione as parcelas acima cuja contribuição nesta fatura substitui o agregado. O total deve ser exato e a operação é atômica.</p><label className="field"><span>Centavos a substituir</span><input type="number" min="1" value={replacementAmount} onChange={(event) => setReplacementAmount(event.target.value)} /></label><button className="primary" disabled={!replacementIds.length} onClick={() => replaceOpening.mutate()}>Confirmar substituição</button></div>}</AsyncState><div className="modal-actions"><button className="ghost" onClick={() => setSelectedInvoice(null)}>Fechar</button></div></section></div>}
      {refundPreview && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true"><h2>Confirmar estorno</h2><p>Crédito: <strong>{formatBrl(refundPreview.result.amount_minor)}</strong>. Elegível restante após: {formatBrl(refundPreview.result.remaining_eligible_minor)}.</p><p>{refundPreview.result.analytical_effect}. A compra original será preservada.</p><div className="modal-actions"><button className="ghost" onClick={() => setRefundPreview(null)}>Voltar</button><button className="primary" onClick={() => confirmRefund.mutate(refundPreview)}>Confirmar estorno</button></div></section></div>}
      {cancelPreview && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true"><h2>Confirmar cancelamento da parcela</h2><p>{formatBrl(cancelPreview.result.amount_minor)} na fatura {formatMonthBr(cancelPreview.result.invoice_month)}. Isso representa obrigação realmente cancelada e não cria estorno adicional.</p><p>Valor ainda elegível: {formatBrl(cancelPreview.result.remaining_eligible_minor)}.</p><div className="modal-actions"><button className="ghost" onClick={() => setCancelPreview(null)}>Voltar</button><button className="danger" onClick={() => confirmCancel.mutate(cancelPreview)}>Confirmar cancelamento</button></div></section></div>}
      {editingCard && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true"><h2>Alterar regra do cartão</h2><p>A nova regra vale para faturas criadas no futuro. Faturas existentes — especialmente liquidadas — não serão movidas silenciosamente.</p><div className="field-row"><label className="field"><span>Fechamento</span><input type="number" min="1" max="31" value={closingDay} onChange={(event) => setClosingDay(Number(event.target.value))} /></label><label className="field"><span>Vencimento</span><input type="number" min="1" max="31" value={dueDay} onChange={(event) => setDueDay(Number(event.target.value))} /></label></div><div className="modal-actions"><button className="ghost" onClick={() => setEditingCard(null)}>Cancelar</button><button className="primary" onClick={() => updateTerms.mutate(editingCard)}>Aplicar a novas faturas</button></div></section></div>}
    </Page>
  );
}
