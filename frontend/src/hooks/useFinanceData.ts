import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import type { Account, Card, Category, Investment, Invoice, Page } from "../api/types";

export const useAccounts = () => useQuery({ queryKey: ["accounts"], queryFn: () => apiFetch<Page<Account>>("/api/v1/accounts"), refetchInterval: 300_000 });
export const useCategories = () => useQuery({ queryKey: ["categories"], queryFn: () => apiFetch<{ items: Category[] }>("/api/v1/categories") });
export const useCards = () => useQuery({ queryKey: ["cards"], queryFn: () => apiFetch<{ items: Card[] }>("/api/v1/cards") });
export const useInvoices = () => useQuery({ queryKey: ["invoices"], queryFn: () => apiFetch<{ items: Invoice[] }>("/api/v1/invoices") });
export const useInvestments = () => useQuery({ queryKey: ["investments"], queryFn: () => apiFetch<{ items: Investment[] }>("/api/v1/investments"), refetchInterval: 300_000 });

