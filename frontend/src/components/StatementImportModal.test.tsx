import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import { setCsrfToken } from "../api/client";
import { StatementImportModal } from "./StatementImportModal";

const response = (body: unknown) => new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });

describe("modal de importação de extrato", () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it("exige prévia e confirmação antes de importar arquivo", async () => {
    let confirmed = false;
    let submittedEdits: Record<string, { description: string; category_id: string | null }> = {};
    setCsrfToken("test-csrf");
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path === "/api/v1/accounts") return Promise.resolve(response({ items: [{ id: "a", name: "Conta teste" }] }));
      if (path === "/api/v1/cards") return Promise.resolve(response({ items: [] }));
      if (path === "/api/v1/categories") return Promise.resolve(response({ items: [{ id: "cat", name: "Mercado", revision: 1, archived_at: null }] }));
      if (path.endsWith("/files/csv")) {
        const form = init?.body as FormData;
        confirmed = form.has("confirmation");
        if (confirmed) submittedEdits = JSON.parse(String(form.get("edits")));
        return Promise.resolve(response(confirmed ? { confirmed: true, result: { new: 1, ignored: 0, financial_created: 1, reconciled: 0 } } : { confirmed: false, confirmation: "signed-preview", total: 1, preview: [{ external_id: "t", date: "2020-01-01", description: "Mercado teste", amount_minor: -100, currency: "BRL", duplicate: false, candidates: [], refund_candidates: [], category_suggestions: [] }] }));
      }
      return Promise.resolve(response({ items: [] }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><StatementImportModal onClose={vi.fn()} /></QueryClientProvider>);
    expect(screen.getByRole("dialog", { name: "Importar arquivo" })).toBeInTheDocument();
    await screen.findByText("Conta · Conta teste");
    fireEvent.change(screen.getByLabelText("Destino do extrato"), { target: { value: "account:a" } });
    fireEvent.change(screen.getByLabelText("Arquivo de extrato"), { target: { files: [new File(["data;descricao;valor\n"], "teste.csv")] } });
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));
    await screen.findByRole("heading", { name: "Visualização prévia" });
    const previewTable = screen.getByRole("table", { name: "Lançamentos que serão salvos" });
    expect(previewTable).toHaveTextContent("Registro");
    expect(previewTable).toHaveTextContent("Categoria");
    expect(previewTable).toHaveTextContent("Conta teste");
    expect(previewTable).toHaveTextContent("Pix");
    expect(previewTable).toHaveTextContent("01/01/2020");
    expect(previewTable).toHaveTextContent("-R$ 1,00");
    expect(previewTable).not.toHaveTextContent("Revisão");
    expect(confirmed).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "Editar nome do registro Mercado teste" }));
    fireEvent.change(screen.getByLabelText("Nome do registro Mercado teste"), { target: { value: "Mercado revisado" } });
    fireEvent.change(screen.getByLabelText("Categoria de Mercado teste"), { target: { value: "cat" } });
    fireEvent.blur(screen.getByLabelText("Nome do registro Mercado teste"));
    expect(previewTable).toHaveTextContent("Mercado revisado");
    expect(previewTable).toHaveTextContent("Mercado");
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    expect(await screen.findByText("1 lançamentos criados; 0 registros ignorados.")).toBeInTheDocument();
    expect(confirmed).toBe(true);
    expect(Object.values(submittedEdits)).toEqual([{ description: "Mercado revisado", category_id: "cat" }]);
  });

  it("separa possíveis correspondências e exige uma decisão", async () => {
    setCsrfToken("test-csrf");
    let submitted: Record<string, unknown> = {};
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path === "/api/v1/accounts") return Promise.resolve(response({ items: [{ id: "a", name: "Conta teste" }] }));
      if (path === "/api/v1/cards") return Promise.resolve(response({ items: [] }));
      if (path.endsWith("/files/csv")) {
        const form = init?.body as FormData;
        if (form.has("confirmation")) {
          submitted = JSON.parse(String(form.get("decisions")));
          return Promise.resolve(response({ confirmed: true, result: { new: 1, ignored: 1, financial_created: 0, reconciled: 0 } }));
        }
        return Promise.resolve(response({ confirmed: false, confirmation: "signed", total: 1, preview: [{ external_id: "match", date: "2026-05-23", description: "Compra CSV", amount_minor: -1000, currency: "BRL", duplicate: false, candidates: [{ kind: "cash_entry", id: "existing", description: "Compra existente", amount_minor: -1000, date: "2026-05-23", status: "effective" }], refund_candidates: [], category_suggestions: [] }] }));
      }
      return Promise.resolve(response({ items: [] }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><StatementImportModal onClose={vi.fn()} /></QueryClientProvider>);
    await screen.findByText("Conta · Conta teste");
    fireEvent.change(screen.getByLabelText("Destino do extrato"), { target: { value: "account:a" } });
    fireEvent.change(screen.getByLabelText("Arquivo de extrato"), { target: { files: [new File(["csv"], "teste.csv")] } });
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));
    expect(await screen.findByRole("heading", { name: "Verificar correspondências" })).toBeInTheDocument();
    expect(screen.getByText("Confira as correspondências entre os dados do novo arquivo com o banco de dados.")).toBeInTheDocument();
    const matches = screen.getByRole("table", { name: "Possíveis correspondências" });
    expect(screen.getAllByText("Dado do arquivo")).toHaveLength(1);
    expect(screen.getAllByText("Correspondente no banco")).toHaveLength(1);
    expect(screen.getByText(/Compra CSV/)).toBeInTheDocument();
    expect(screen.getByText(/Compra existente/)).toBeInTheDocument();
    expect(matches).toBeInTheDocument();
    const next = screen.getByRole("button", { name: "Continuar" });
    expect(next).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    expect(next).toBeEnabled();
    fireEvent.click(screen.getByRole("button", { name: "Ignorar" }));
    expect(next).toBeEnabled();
    fireEvent.click(next);
    fireEvent.click(screen.getByRole("button", { name: "Salvar" }));
    await screen.findByText(/1 registros ignorados/);
    expect(submitted).toEqual({ match: { action: "ignore" } });
  });

  it("apresenta o mapeamento automático e permite corrigir a prévia", async () => {
    setCsrfToken("test-csrf");
    const mappings: string[] = [];
    vi.spyOn(globalThis, "fetch").mockImplementation((input, init) => {
      const path = String(input);
      if (path === "/api/v1/accounts") return Promise.resolve(response({ items: [] }));
      if (path === "/api/v1/cards") return Promise.resolve(response({ items: [{ id: "c", name: "Cartão teste" }] }));
      if (path.endsWith("/files/csv")) {
        const form = init?.body as FormData;
        mappings.push(String(form.get("mapping")));
        return Promise.resolve(response({ confirmed: false, confirmation: "signed", total: 2, csv_analysis: { headers: ["date", "title", "amount"], mapping: { date: "date", description: "title", amount: "amount", id: "" }, confidence: { date: 1, description: 1, amount: 1 }, encoding: "UTF-8", delimiter: "vírgula", preset: "nubank_card", invert_signs: true, warnings: ["Formato reconhecido"], row_count: 2 }, preview: [{ external_id: "1", date: "2020-01-01", description: "Compra", amount_minor: -100, currency: "BRL", duplicate: false, candidates: [], category_suggestions: [] }] }));
      }
      return Promise.resolve(response({ items: [] }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><StatementImportModal onClose={vi.fn()} /></QueryClientProvider>);
    await screen.findByText("Cartão · Cartão teste");
    fireEvent.change(screen.getByLabelText("Destino do extrato"), { target: { value: "card:c" } });
    fireEvent.change(screen.getByLabelText("Arquivo de extrato"), { target: { files: [new File(["date,title,amount\n"], "fatura.csv")] } });
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));
    expect(await screen.findByRole("heading", { name: "Revisar leitura do CSV" })).toBeInTheDocument();
    expect(screen.getByText("Formato reconhecido")).toBeInTheDocument();
    expect(screen.getByLabelText("Inverter sinais dos valores")).toBeChecked();
    expect(mappings[0]).toBe("{}");
    fireEvent.change(screen.getByLabelText(/^Coluna descrição/), { target: { value: "date" } });
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));
    await screen.findByRole("heading", { name: "Visualização prévia" });
    expect(JSON.parse(mappings[1] ?? "{}").description).toBe("date");
  });

  it("impede continuar quando o arquivo não corresponde ao destino", async () => {
    setCsrfToken("test-csrf");
    vi.spyOn(globalThis, "fetch").mockImplementation((input) => {
      const path = String(input);
      if (path === "/api/v1/accounts") return Promise.resolve(response({ items: [] }));
      if (path === "/api/v1/cards") return Promise.resolve(response({ items: [{ id: "c", name: "Cartão teste" }] }));
      if (path.endsWith("/files/csv")) return Promise.resolve(new Response(JSON.stringify({ detail: { code: "VALIDATION_ERROR", message: "O arquivo parece ser um extrato de conta bancária, mas o destino selecionado é cartão. Selecione o destino correspondente antes de continuar." } }), { status: 422, headers: { "Content-Type": "application/json" } }));
      return Promise.resolve(response({ items: [] }));
    });
    const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
    render(<QueryClientProvider client={client}><StatementImportModal onClose={vi.fn()} /></QueryClientProvider>);
    await screen.findByText("Cartão · Cartão teste");
    fireEvent.change(screen.getByLabelText("Destino do extrato"), { target: { value: "card:c" } });
    fireEvent.change(screen.getByLabelText("Arquivo de extrato"), { target: { files: [new File(["pix"], "conta.csv")] } });
    fireEvent.click(screen.getByRole("button", { name: "Continuar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("extrato de conta bancária");
    expect(screen.getByRole("heading", { name: "Importar arquivo" })).toBeInTheDocument();
  });
});
