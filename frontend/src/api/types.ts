export type Page<T> = { items: T[]; page: number; page_size: number; total: number };

export type Account = {
  id: string; name: string; institution: string | null; reference_date: string;
  reference_balance_minor: number; current_balance_minor: number; revision: number; archived_at: string | null;
};
export type Category = { id: string; name: string; kind: "income" | "expense"; revision: number; archived_at: string | null };
export type Card = {
  id: string; name: string; limit_minor: number; closing_day: number; due_day: number;
  default_account_id: string | null; commitment_minor: number; available_estimated_minor: number; revision: number; archived_at: string | null;
};
export type CashEntry = {
  id: string; description: string; kind: string; signed_amount_minor: number; planned_date: string;
  effective_date: string | null; status: string; account_id: string; category_id: string | null; source: string; revision: number;
};
export type Invoice = {
  id: string; card_id: string; reference_month: string; closing_date: string; due_date: string;
  state: "open" | "closed" | "settled"; net_minor: number; payable_minor: number; revision: number; dependency_warning?: string | null;
};
export type Purchase = { id: string; card_id: string; description: string; purchase_date: string; total_minor: number; installment_count: number; category_id: string | null; revision: number };
export type Installment = { id: string; purchase_id: string; invoice_id: string; installment_number: number; amount_minor: number; status: string; revision: number };
