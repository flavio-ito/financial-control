import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "../api/client";
import { useAccounts, useCards, useCategories } from "../hooks/useFinanceData";
import { formatDateBr } from "../lib/dates";
import { formatBrl } from "../lib/money";

type Candidate = { id: string; description: string; amount_minor: number; date?: string | null };
type Columns = { date: string; description: string; amount: string; id: string };
type Decision = { action: "insert" | "ignore"; target_id?: string };
type RowEdit = { description: string; category_id: string | null };
type DescriptionEdit = { rowId: string; value: string };
type CsvAnalysis = { headers: string[]; mapping: Columns; confidence: Partial<Record<keyof Columns, number>>; encoding: string; delimiter: string; preset: string | null; invert_signs: boolean; warnings: string[]; row_count: number };
type PreviewRow = { external_id: string; date: string; description: string; amount_minor: number; currency: string; duplicate: boolean; candidates: Candidate[]; refund_candidates?: Candidate[]; category_suggestions?: { category_id: string; category_name: string }[] };
type Preview = { confirmation: string | null; total: number; csv_analysis?: CsvAnalysis | null; preview: PreviewRow[] };
type Run = { financial_created: number; reconciled: number; ignored: number };
type UploadRequest = { confirm: boolean; csvReviewed?: boolean };
const base = "/api/v1/integrations";
const emptyColumns: Columns = { date: "", description: "", amount: "", id: "" };
const stepTitles = { 1: "Importar arquivo", 2: "Revisar leitura do CSV", 3: "Verificar correspondências", 4: "Visualização prévia" } as const;
const errorMessage = (error: unknown) => error instanceof ApiError ? error.message : "Não foi possível importar o arquivo.";
const RecordDetails = ({ date, description, amount }: { date?: string | null; description: string; amount: number }) => <div className="import-record-details"><time dateTime={date ?? undefined}>{date ? formatDateBr(date) : "—"}</time><span>{description}</span><strong className={amount < 0 ? "negative" : "positive"}>{formatBrl(amount)}</strong></div>;

export function StatementImportModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const accounts = useAccounts();
  const cards = useCards();
  const categories = useCategories();
  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [file, setFile] = useState<File | null>(null);
  const [format, setFormat] = useState("csv");
  const [target, setTarget] = useState("");
  const [columns, setColumns] = useState<Columns>(emptyColumns);
  const [analysis, setAnalysis] = useState<CsvAnalysis | null>(null);
  const [analysisApplied, setAnalysisApplied] = useState(false);
  const [invertSigns, setInvertSigns] = useState(false);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [rowEdits, setRowEdits] = useState<Record<string, RowEdit>>({});
  const [descriptionEdit, setDescriptionEdit] = useState<DescriptionEdit | null>(null);
  const [message, setMessage] = useState("");
  const [targetKind, targetId] = target.split(":");
  const selectedCard = targetKind === "card" ? cards.data?.items.find(card => card.id === targetId) : undefined;
  const selectedAccount = targetKind === "account" ? accounts.data?.items.find(account => account.id === targetId) : accounts.data?.items.find(account => account.id === selectedCard?.default_account_id);
  const targetBank = selectedAccount?.institution ?? selectedAccount?.name ?? "—";
  const paymentMethod = selectedCard?.name ?? "Pix";
  const newRows = preview?.preview.filter(row => !row.duplicate && row.candidates.length === 0 && !(targetKind === "card" && row.amount_minor > 0)) ?? [];
  const attentionRows = preview?.preview.filter(row => !row.duplicate && (row.candidates.length > 0 || (targetKind === "card" && row.amount_minor > 0))) ?? [];
  const duplicateCount = preview?.preview.filter(row => row.duplicate).length ?? 0;
  const validDecision = (row: PreviewRow) => { const decision = decisions[row.external_id]; if (!decision) return false; return decision.action === "ignore" || row.amount_minor <= 0 || (row.refund_candidates ?? []).some(item => item.id === decision.target_id); };
  const canContinue = attentionRows.every(validDecision);
  const finalRows = [...newRows, ...attentionRows.filter(row => decisions[row.external_id]?.action === "insert")];
  const rowEdit = (row: PreviewRow): RowEdit => rowEdits[row.external_id] ?? { description: row.description, category_id: row.category_suggestions?.[0]?.category_id ?? null };
  const validRowEdits = finalRows.every(row => rowEdit(row).description.trim());
  const ignoredMatches = attentionRows.filter(row => decisions[row.external_id]?.action === "ignore").length;
  const reset = () => { setStep(1); setPreview(null); setDecisions({}); setRowEdits({}); setDescriptionEdit(null); setAnalysis(null); setAnalysisApplied(false); setColumns(emptyColumns); setInvertSigns(false); };

  const upload = useMutation({
    mutationFn: async ({ confirm }: UploadRequest) => {
      if (!file) throw new Error("Selecione um arquivo.");
      const body = new FormData(); body.append("file", file);
      const [kind, id] = target.split(":"); if (!id) throw new Error("Selecione um destino.");
      body.append(kind === "account" ? "account_id" : "card_id", id);
      body.append("mapping", JSON.stringify(format === "csv" && analysisApplied ? columns : {}));
      if (format === "csv" && analysisApplied) body.append("invert_signs", String(invertSigns));
      if (confirm && preview?.confirmation) { body.append("confirmation", preview.confirmation); body.append("decisions", JSON.stringify(decisions)); body.append("edits", JSON.stringify(Object.fromEntries(finalRows.map(row => [row.external_id, rowEdit(row)])))); }
      return apiFetch<Preview & { confirmed: boolean; result: Run }>(`${base}/files/${format}`, { method: "POST", body });
    },
    onMutate: () => setMessage(""),
    onSuccess: async (data, request) => {
      if (!data.confirmed) {
        if (data.csv_analysis) { setAnalysis(data.csv_analysis); setColumns(data.csv_analysis.mapping); setInvertSigns(data.csv_analysis.invert_signs); setAnalysisApplied(true); }
        setPreview(data.confirmation ? data : null); setDecisions({}); setRowEdits({}); setDescriptionEdit(null);
        const attention = data.preview.some(row => !row.duplicate && (row.candidates.length > 0 || (target.startsWith("card:") && row.amount_minor > 0)));
        setStep(format === "csv" && data.csv_analysis && !request.csvReviewed ? 2 : attention ? 3 : 4); return;
      }
      setPreview(null); setMessage(`${data.result.financial_created} lançamentos criados; ${data.result.ignored} registros ignorados.`); await queryClient.invalidateQueries();
    },
  });
  const busy = upload.isPending;
  const choose = (row: PreviewRow, action: Decision["action"]) => { const options = action === "insert" ? row.refund_candidates ?? [] : []; setDecisions({...decisions, [row.external_id]: { action, target_id: options.length === 1 ? options[0]?.id : undefined }}); };
  const finishDescriptionEdit = () => {
    if (!descriptionEdit?.value.trim()) return;
    const row = finalRows.find(item => item.external_id === descriptionEdit.rowId);
    if (!row) return;
    setRowEdits(current => ({...current, [row.external_id]: {...rowEdit(row), description: descriptionEdit.value.trim()}}));
    setDescriptionEdit(null);
  };

  return <div className="modal-backdrop"><section className={`modal transaction-modal statement-import-modal statement-import-step-${step}`} role="dialog" aria-modal="true" aria-labelledby="statement-import-title"><h2 id="statement-import-title">{stepTitles[step]}</h2><form onSubmit={event => { event.preventDefault(); setPreview(null); upload.mutate({ confirm: false }); }}>
    {step === 1 && <><div className="field-row"><label className="field"><span>Formato do extrato</span><select value={format} disabled={busy} onChange={event => { setFormat(event.target.value); setFile(null); reset(); }}><option value="csv">CSV</option><option value="ofx">OFX</option></select></label><label className="field"><span>Destino do extrato</span><select value={target} disabled={busy} onChange={event => { setTarget(event.target.value); reset(); }}><option value="">Selecione</option>{accounts.data?.items.map(account => <option key={account.id} value={`account:${account.id}`}>Conta · {account.name}</option>)}{cards.data?.items.map(card => <option key={card.id} value={`card:${card.id}`}>Cartão · {card.name}</option>)}</select></label></div><label className="field"><span>Arquivo de extrato</span><input key={format} type="file" accept={format === "csv" ? ".csv,text/csv" : ".ofx,application/x-ofx"} disabled={busy} onChange={event => { setFile(event.target.files?.[0] ?? null); reset(); }} /></label></>}
    {step === 2 && analysis && <section className="import-csv-review" aria-label="Configuração da leitura do CSV"><p className="import-step-subtitle">Confira se cada informação foi associada à coluna correta antes de continuar.</p>{analysis.warnings.length > 0 && <div className="import-analysis-warning" role="status">{analysis.warnings.map(item => <p key={item}>{item}</p>)}</div>}<div className="field-row import-column-fields">{(Object.keys(columns) as (keyof Columns)[]).map(key => <label className="field" key={key}><span>Coluna {({date:"data",description:"descrição",amount:"valor",id:"identificador (opcional)"})[key]}</span><select value={columns[key]} disabled={busy} onChange={event => { setColumns(current => ({...current,[key]:event.target.value})); setAnalysisApplied(true); }}><option value="">Não identificada</option>{analysis.headers.map(header => <option key={header} value={header}>{header}</option>)}</select></label>)}</div><label className="check-row"><input type="checkbox" checked={invertSigns} disabled={busy} onChange={event => { setInvertSigns(event.target.checked); setAnalysisApplied(true); }} />Inverter sinais dos valores</label><div className="movement-list import-mapping-preview" role="table" aria-label="Prévia do cabeçalho do CSV"><div className="movement-list-header" role="row"><span role="columnheader">Data</span><span role="columnheader">Registro</span><span role="columnheader">Valor</span><span role="columnheader">Identificador</span></div><div className="movement-row" role="row"><span role="cell">{columns.date || "Não definida"}</span><span role="cell">{columns.description || "Não definida"}</span><span role="cell">{columns.amount || "Não definida"}</span><span role="cell" className={!columns.id ? "muted" : undefined}>{columns.id || "Opcional"}</span></div></div></section>}
    {step === 3 && <section className="import-attention"><p>Confira as correspondências entre os dados do novo arquivo com o banco de dados.</p><div className="import-match-table" role="table" aria-label="Possíveis correspondências"><div className="import-match-table-header" role="row"><strong role="columnheader">Dado do arquivo</strong><strong role="columnheader">Correspondente no banco</strong><strong role="columnheader">Ação</strong></div>{attentionRows.map(row => { const decision = decisions[row.external_id]; const refunds = row.refund_candidates ?? []; const canSave = row.amount_minor <= 0 || refunds.length > 0; return <article className="import-match-row" role="row" key={row.external_id}><div role="cell"><RecordDetails date={row.date} description={row.description} amount={row.amount_minor} /></div><div role="cell">{row.candidates.length > 0 ? row.candidates.map(item => <RecordDetails key={item.id} date={item.date} description={item.description} amount={item.amount_minor} />) : <p>Nenhum lançamento correspondente.</p>}</div><div className="import-match-actions" role="cell"><button type="button" className={`import-decision-button${decision?.action === "insert" ? " is-selected" : ""}`} aria-pressed={decision?.action === "insert"} disabled={busy || !canSave} onClick={() => choose(row, "insert")}>Salvar</button><button type="button" className={`import-decision-button${decision?.action === "ignore" ? " is-selected" : ""}`} aria-pressed={decision?.action === "ignore"} disabled={busy} onClick={() => choose(row, "ignore")}>Ignorar</button>{decision?.action === "insert" && row.amount_minor > 0 && <label className="field"><span>Compra original do estorno</span><select value={decision.target_id ?? ""} onChange={event => setDecisions({...decisions, [row.external_id]: { action: "insert", target_id: event.target.value }})}><option value="">Selecione</option>{refunds.map(item => <option key={item.id} value={item.id}>{item.description} · {formatBrl(item.amount_minor)}</option>)}</select></label>}{row.amount_minor > 0 && refunds.length === 0 && <p className="field-error">Nenhuma compra compatível foi encontrada para este estorno.</p>}</div></article>; })}</div></section>}
    {step === 4 && preview && <section className="restore-confirm"><p className="import-preview-hint">Clique no nome ou na categoria para editar.</p><div className="integration-preview movement-list import-preview-list" role="table" aria-label="Lançamentos que serão salvos"><div className="movement-list-header" role="row"><span>Registro</span><span>Categoria</span><span>Banco</span><span>Forma de pagamento</span><span>Data</span><span>Valor</span></div>{finalRows.map((row, index) => { const edit = rowEdit(row); const isEditingDescription = descriptionEdit?.rowId === row.external_id; const editorPosition = index === 0 ? " is-first" : index === finalRows.length - 1 ? " is-last" : ""; return <article className="movement-row" role="row" key={row.external_id}><div className="import-description-cell"><button type="button" className="import-preview-description" aria-label={`Editar nome do registro ${edit.description}`} aria-expanded={isEditingDescription} title={edit.description} disabled={busy} onClick={() => setDescriptionEdit({ rowId: row.external_id, value: edit.description })}>{edit.description}</button>{isEditingDescription && <textarea className={`import-description-editor${editorPosition}`} aria-label={`Nome do registro ${row.description}`} autoFocus value={descriptionEdit.value} disabled={busy} onChange={event => setDescriptionEdit({...descriptionEdit, value: event.target.value})} onBlur={finishDescriptionEdit} onKeyDown={event => { if (event.key === "Escape") setDescriptionEdit(null); if (event.key === "Enter") { event.preventDefault(); event.currentTarget.blur(); } }} />}</div><select className="import-preview-select import-preview-inline-control" aria-label={`Categoria de ${row.description}`} title="Clique para editar a categoria" value={edit.category_id ?? ""} disabled={busy || categories.isPending} onChange={event => setRowEdits(current => ({...current, [row.external_id]: {...edit, category_id: event.target.value || null}}))}><option value="">Sem categoria</option>{categories.data?.items.filter(category => !category.archived_at).map(category => <option key={category.id} value={category.id}>{category.name}</option>)}</select><span title={selectedAccount?.name}>{targetBank}</span><span>{paymentMethod}</span><time dateTime={row.date}>{formatDateBr(row.date)}</time><span className={row.amount_minor < 0 ? "negative" : "positive"}>{formatBrl(row.amount_minor)}</span></article>; })}</div></section>}
    {busy && <p role="status">Processando importação…</p>}{message && <p className="success" role="status">{message}</p>}{upload.isError && <p className="field-error" role="alert">{errorMessage(upload.error)}</p>}
    <div className="modal-actions"><button type="button" className="ghost overview-new-transaction" disabled={busy} onClick={onClose}>{message ? "Fechar" : "Cancelar"}</button>{!message && step > 1 && <button type="button" className="secondary overview-new-transaction" disabled={busy} onClick={() => setStep(step === 2 ? 1 : step === 3 ? (format === "csv" ? 2 : 1) : attentionRows.length > 0 ? 3 : format === "csv" ? 2 : 1)}>Voltar</button>}{!message && step === 1 && <button className="primary overview-new-transaction" type="submit" disabled={busy || !file || !target}>Continuar</button>}{!message && step === 2 && <button type="button" className="primary overview-new-transaction" disabled={busy || !columns.date || !columns.description || !columns.amount} onClick={() => upload.mutate({ confirm: false, csvReviewed: true })}>{busy ? "Atualizando…" : "Continuar"}</button>}{!message && step === 3 && <button type="button" className="primary overview-new-transaction" disabled={busy || !canContinue} onClick={() => setStep(4)}>Continuar</button>}{!message && step === 4 && preview && <button type="button" className="primary overview-new-transaction" disabled={busy || !canContinue || !validRowEdits} onClick={() => upload.mutate({ confirm: true })}>Salvar</button>}</div>
  </form></section></div>;
}
