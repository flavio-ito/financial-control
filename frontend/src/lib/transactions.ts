export type TransactionDirection = "Entrada" | "Despesa";

const ENTRY_KINDS = new Set(["income", "transfer_in", "refund"]);
const EXPENSE_KINDS = new Set(["expense", "card_purchase", "transfer_out", "invoice_payment"]);

export function transactionDirection(kind: string, signedAmountMinor: number): TransactionDirection {
  if (ENTRY_KINDS.has(kind)) return "Entrada";
  if (EXPENSE_KINDS.has(kind)) return "Despesa";

  return signedAmountMinor < 0 ? "Despesa" : "Entrada";
}
