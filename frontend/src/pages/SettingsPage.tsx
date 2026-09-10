import { ChangeEvent, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ApiError, apiDownload, apiFetch } from "../api/client";
import { Page } from "../components/Page";
import { useAccounts, useCards } from "../hooks/useFinanceData";
import { formatDateBr } from "../lib/dates";
import { todayIso } from "../lib/forms";

type Status = { app_id: string; data_directory: string };
type RestorePreview = {
  restore_token: string;
  filename: string;
  size_bytes: number;
  manifest: { created_at_utc: string; app_version: string; alembic_revision: string };
  warning: string;
};
type Coverage = { id: string; account_id: string | null; card_id: string | null; date_from: string; date_to: string; status: "complete" | "partial" | "unknown"; note: string | null };

function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Não foi possível concluir a operação.";
}

export function SettingsPage() {
  const [preview, setPreview] = useState<RestorePreview | null>(null);
  const [message, setMessage] = useState("");
  const [coverageSource, setCoverageSource] = useState("");
  const [coverageFrom, setCoverageFrom] = useState(todayIso().slice(0, 8) + "01");
  const [coverageTo, setCoverageTo] = useState(todayIso());
  const [coverageStatus, setCoverageStatus] = useState<Coverage["status"]>("unknown");
  const accounts = useAccounts();
  const cards = useCards();
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["status"], queryFn: () => apiFetch<Status>("/api/v1/status") });
  const coverage = useQuery({ queryKey: ["coverage"], queryFn: () => apiFetch<{ items: Coverage[] }>("/api/v1/coverage") });
  const shutdown = useMutation({ mutationFn: () => apiFetch("/api/v1/application/shutdown", { method: "POST" }) });
  const exportBackup = useMutation({
    mutationFn: () => apiDownload("/api/v1/backups/export", { method: "POST" }),
    onSuccess: ({ blob, filename }) => {
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
      setMessage("Backup exportado e validado.");
    },
  });
  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("backup", file);
      return apiFetch<RestorePreview>("/api/v1/backups/restore/preview", { method: "POST", body: form });
    },
    onSuccess: (result) => { setPreview(result); setMessage(""); },
  });
  const restore = useMutation({
    mutationFn: () => apiFetch<{ status: string }>("/api/v1/backups/restore/confirm", { method: "POST", body: JSON.stringify({ restore_token: preview?.restore_token }) }),
    onSuccess: () => { setPreview(null); setMessage("Restauração concluída. Recarregue a página para reler todos os dados."); },
  });
  const saveCoverage = useMutation({ mutationFn: () => {
    const [kind, id] = coverageSource.split(":");
    return apiFetch("/api/v1/coverage", { method: "POST", body: JSON.stringify({ account_id: kind === "account" ? id : null, card_id: kind === "card" ? id : null, date_from: coverageFrom, date_to: coverageTo, status: coverageStatus, note: null }) });
  }, onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["coverage"] }) });

  function chooseFile(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) upload.mutate(file);
    event.target.value = "";
  }

  const operationError = exportBackup.error ?? upload.error ?? restore.error;
  return <Page eyebrow="Privacidade e recuperação" title="Configurações e dados" description="O arquivo local não tem criptografia própria; proteja sua sessão e seu disco.">
    <div className="settings-grid">
      <section className="panel"><h2>Armazenamento local</h2><dl><dt>APP_ID estável</dt><dd>{status.data?.app_id ?? "…"}</dd><dt>Pasta de dados</dt><dd className="path">{status.data?.data_directory ?? "Carregando…"}</dd><dt>Idioma e moeda</dt><dd>Português do Brasil · BRL</dd></dl></section>
      <section className="panel"><h2>Backup e restauração</h2><p>Backups automáticos diários mantêm 30 cópias. Exporte uma cópia para outro dispositivo.</p>
        <div className="button-row"><button className="primary" disabled={exportBackup.isPending} onClick={() => exportBackup.mutate()}>{exportBackup.isPending ? "Exportando…" : "Exportar backup"}</button><label className="button secondary">Selecionar .finbackup<input className="visually-hidden" type="file" accept=".finbackup" onChange={chooseFile} /></label></div>
        {preview && <div className="restore-confirm" role="alert"><strong>Confirme a substituição completa dos dados</strong><p>{preview.filename} · {(preview.size_bytes / 1024).toFixed(1)} KB · criado em {new Date(preview.manifest.created_at_utc).toLocaleString("pt-BR")}</p><p>{preview.warning}</p><div className="button-row"><button className="danger" disabled={restore.isPending} onClick={() => restore.mutate()}>{restore.isPending ? "Restaurando…" : "Sim, restaurar este backup"}</button><button className="secondary" onClick={() => setPreview(null)}>Cancelar</button></div></div>}
        {message && <p className="success" role="status">{message}</p>}{operationError && <p className="error" role="alert">{errorMessage(operationError)}</p>}
      </section>
      <section className="panel"><h2>Cobertura do histórico</h2><p>Declare o que você informou; a existência de lançamentos não certifica completude.</p><label className="field"><span>Conta ou cartão</span><select value={coverageSource} onChange={(event) => setCoverageSource(event.target.value)}><option value="">Selecione</option>{accounts.data?.items.map((item) => <option key={item.id} value={`account:${item.id}`}>Conta · {item.name}</option>)}{cards.data?.items.map((item) => <option key={item.id} value={`card:${item.id}`}>Cartão · {item.name}</option>)}</select></label><div className="field-row"><label className="field"><span>De</span><input type="date" value={coverageFrom} onChange={(event) => setCoverageFrom(event.target.value)} /></label><label className="field"><span>Até</span><input type="date" value={coverageTo} onChange={(event) => setCoverageTo(event.target.value)} /></label></div><label className="field"><span>Qualidade declarada</span><select value={coverageStatus} onChange={(event) => setCoverageStatus(event.target.value as Coverage["status"])}><option value="complete">Completa</option><option value="partial">Parcial</option><option value="unknown">Desconhecida</option></select></label><button className="primary" disabled={!coverageSource || saveCoverage.isPending} onClick={() => saveCoverage.mutate()}>Registrar intervalo</button><div className="list">{coverage.data?.items.map((item) => <article className="list-row" key={item.id}><div><strong>{item.status === "complete" ? "Completa declarada" : item.status === "partial" ? "Parcial" : "Desconhecida"}</strong><small>{formatDateBr(item.date_from)} a {formatDateBr(item.date_to)}</small></div></article>)}</div></section>
      <section className="panel danger-zone"><h2>Encerrar aplicativo</h2><p>Fechar a aba não encerra o servidor local.</p><button className="danger" disabled={shutdown.isPending || shutdown.isSuccess} onClick={() => shutdown.mutate()}>{shutdown.isSuccess ? "Aplicativo encerrando…" : "Encerrar com segurança"}</button></section>
    </div>
  </Page>;
}
