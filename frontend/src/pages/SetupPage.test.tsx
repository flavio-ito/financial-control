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

  it("converte BRL em centavos, persiste a conta e avança sem duplicar", async () => {
    setCsrfToken("csrf-test");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path === "/api/v1/status") return response({ data_directory: "C:/dados/teste" });
      if (path === "/api/v1/accounts" && init?.method === "POST") return response({ id: "account-1" });
      if (path === "/api/v1/accounts") return response({ items: [], page: 1, page_size: 50, total: 0 });
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
    fireEvent.click(screen.getByRole("button", { name: "Salvar e continuar" }));
    await screen.findByRole("heading", { name: "Configure seus cartões" });
    const accountCall = fetchMock.mock.calls.find(([path, init]) => String(path) === "/api/v1/accounts" && init?.method === "POST");
    expect(accountCall).toBeDefined();
    const body = JSON.parse(String(accountCall?.[1]?.body));
    expect(body.reference_balance_minor).toBe(12345);
    expect(body.reference_date).toBe("2026-09-08");
    await waitFor(() => expect(fetchMock.mock.calls.filter(([path, init]) => String(path) === "/api/v1/accounts" && init?.method === "POST")).toHaveLength(1));
  });

  it("permite cadastrar um cartão durante o onboarding e depois continuar", async () => {
    setCsrfToken("csrf-test");
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const path = String(input);
      if (path === "/api/v1/status") return response({ data_directory: "C:/dados/teste" });
      if (path === "/api/v1/accounts") return response({ items: [{ id: "account-1", name: "Conta principal" }], page: 1, page_size: 50, total: 1 });
      if (path === "/api/v1/cards" && init?.method === "POST") return response({ id: "card-1" });
      if (path === "/api/v1/cards") return response({ items: [] });
      if (path === "/api/v1/categories") return response({ items: [] });
      if (path === "/api/v1/setup") return response({ setup_step: 3 });
      throw new Error(`URL inesperada: ${path} ${init?.method}`);
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><SetupPage initialStep={2} /></QueryClientProvider>);
    await screen.findByRole("option", { name: "Conta principal" });
    fireEvent.change(screen.getByLabelText("Nome do cartão"), { target: { value: "Cartão principal" } });
    fireEvent.change(screen.getByLabelText(/Limite/), { target: { value: "R$ 2.500,00" } });
    fireEvent.change(screen.getByLabelText("Conta habitual para pagamento"), { target: { value: "account-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Adicionar cartão" }));
    await waitFor(() => expect(fetchMock.mock.calls.some(([path, init]) => String(path) === "/api/v1/cards" && init?.method === "POST")).toBe(true));
    const cardCall = fetchMock.mock.calls.find(([path, init]) => String(path) === "/api/v1/cards" && init?.method === "POST");
    expect(JSON.parse(String(cardCall?.[1]?.body))).toMatchObject({ name: "Cartão principal", limit_minor: 250000, default_account_id: "account-1" });
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));
    await screen.findByRole("heading", { name: "Crie suas categorias" });
  });
});
