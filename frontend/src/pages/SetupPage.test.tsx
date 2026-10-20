import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setCsrfToken } from "../api/client";
import { SetupPage } from "./SetupPage";

function response(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

describe("assistente de primeiro acesso", () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("permite cadastrar várias contas antes de continuar", async () => {
    setCsrfToken("csrf-test");
    const savedAccounts: { id: string; name: string; institution: string | null }[] = [];
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path === "/api/v1/status") return response({ data_directory: "C:/dados/teste" });
      if (path === "/api/v1/accounts" && init?.method === "POST") {
        const body = JSON.parse(String(init.body));
        const account = { id: `account-${savedAccounts.length + 1}`, name: body.name, institution: body.institution };
        savedAccounts.push(account);
        return response(account);
      }
      if (path === "/api/v1/accounts") return response({ items: savedAccounts, page: 1, page_size: 50, total: savedAccounts.length });
      if (path === "/api/v1/cards") return response({ items: [] });
      if (path === "/api/v1/categories") return response({ items: [] });
      if (path === "/api/v1/setup") return response({ setup_step: 2 });
      throw new Error(`URL inesperada: ${path} ${init?.method}`);
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><SetupPage initialStep={1} /></QueryClientProvider>);
    fireEvent.change(screen.getByLabelText("Nome da conta"), { target: { value: "Conta principal" } });
    fireEvent.change(screen.getByLabelText(/Saldo inicial da data/), { target: { value: "R$ 123,45" } });
    fireEvent.change(screen.getByLabelText("Data de referência"), { target: { value: "2026-09-08" } });
    fireEvent.click(screen.getByRole("button", { name: "Adicionar conta" }));
    await screen.findByText("Conta principal");
    const accountCall = fetchMock.mock.calls.find(([path, init]) => String(path) === "/api/v1/accounts" && init?.method === "POST");
    expect(accountCall).toBeDefined();
    const body = JSON.parse(String(accountCall?.[1]?.body));
    expect(body.reference_balance_minor).toBe(12345);
    expect(body.reference_date).toBe("2026-09-08");
    fireEvent.change(screen.getByLabelText("Nome da conta"), { target: { value: "Conta reserva" } });
    fireEvent.click(screen.getByRole("button", { name: "Adicionar conta" }));
    await screen.findByText("Conta reserva");
    expect(fetchMock.mock.calls.filter(([path, init]) => String(path) === "/api/v1/accounts" && init?.method === "POST")).toHaveLength(2);
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));
    await screen.findByRole("heading", { name: "Configure seus cartões" });
  });

  it("permite cadastrar um cartão durante o onboarding e depois continuar", async () => {
    setCsrfToken("csrf-test");
    const savedCards: Record<string, unknown>[] = [];
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path === "/api/v1/status") return response({ data_directory: "C:/dados/teste" });
      if (path === "/api/v1/accounts") return response({ items: [{ id: "account-1", name: "Conta principal", institution: "Banco Teste" }], page: 1, page_size: 50, total: 1 });
      if (path === "/api/v1/cards" && init?.method === "POST") {
        const card = { id: "card-1", ...JSON.parse(String(init.body)) };
        savedCards.push(card);
        return response(card);
      }
      if (path === "/api/v1/cards") return response({ items: savedCards });
      if (path === "/api/v1/categories") return response({ items: [] });
      if (path === "/api/v1/setup") return response({ setup_step: 3 });
      throw new Error(`URL inesperada: ${path} ${init?.method}`);
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><SetupPage initialStep={2} /></QueryClientProvider>);
    await screen.findByRole("option", { name: "Banco Teste" });
    fireEvent.change(screen.getByLabelText("Nome"), { target: { value: "Cartão principal" } });
    fireEvent.change(screen.getByLabelText("Banco"), { target: { value: "account-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Adicionar cartão" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([path, init]) => String(path) === "/api/v1/cards" && init?.method === "POST")).toBe(true));
    expect(await screen.findByText("Cartão principal")).toBeInTheDocument();
    const cardCall = fetchMock.mock.calls.find(([path, init]) => String(path) === "/api/v1/cards" && init?.method === "POST");
    expect(JSON.parse(String(cardCall?.[1]?.body))).toEqual({ name: "Cartão principal", limit_minor: 0, closing_day: 10, due_day: 20, default_account_id: "account-1" });
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));
    await screen.findByRole("heading", { name: "Crie suas categorias" });
  });

  it("permite voltar para a etapa anterior sem alterar o progresso salvo", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const path = String(input);
      if (path === "/api/v1/status") return response({ data_directory: "C:/dados/teste" });
      if (path === "/api/v1/accounts") return response({ items: [{ id: "account-1", name: "Conta principal", institution: "Banco Teste" }], page: 1, page_size: 50, total: 1 });
      if (path === "/api/v1/cards") return response({ items: [] });
      if (path === "/api/v1/categories") return response({ items: [] });
      throw new Error(`URL inesperada: ${path}`);
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><SetupPage initialStep={2} /></QueryClientProvider>);
    fireEvent.click(screen.getByRole("button", { name: "Voltar" }));
    await screen.findByRole("heading", { name: "Cadastre suas contas" });
  });
});
