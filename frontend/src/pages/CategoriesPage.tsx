import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { apiFetch } from "../api/client";
import type { Category } from "../api/types";
import { AsyncState } from "../components/AsyncState";
import { Page } from "../components/Page";
import { useCategories } from "../hooks/useFinanceData";

type Values = { name: string; kind: "expense" | "income" };
export function CategoriesPage() {
  const categories = useCategories();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Category | null>(null);
  const [name, setName] = useState("");
  const form = useForm<Values>({ defaultValues: { name: "", kind: "expense" } });
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["categories"] });
  const save = useMutation({ mutationFn: (v: Values) => apiFetch("/api/v1/categories", { method: "POST", body: JSON.stringify(v) }), onSuccess: () => { form.reset(); refresh(); } });
  const rename = useMutation({ mutationFn: (item: Category) => apiFetch(`/api/v1/categories/${item.id}`, { method: "PUT", body: JSON.stringify({ name, expected_revision: item.revision }) }), onSuccess: () => { setEditing(null); refresh(); } });
  const archive = useMutation({ mutationFn: (item: Category) => apiFetch(`/api/v1/categories/${item.id}/archive`, { method: "POST", body: JSON.stringify({ expected_revision: item.revision, reason: "Arquivada pelo usuário" }) }), onSuccess: refresh });
  return <Page eyebrow="Classificação" title="Categorias" description="Sem categoria é uma ausência explícita e continua visível.">
    <div className="grid-form"><form className="panel form-panel" onSubmit={form.handleSubmit((v) => save.mutate(v))}><h2>Nova categoria</h2><label className="field"><span>Nome</span><input required {...form.register("name")} /></label><label className="field"><span>Tipo</span><select {...form.register("kind")}><option value="expense">Despesa</option><option value="income">Receita</option></select></label><button className="primary">Salvar categoria</button></form>
      <section className="panel"><h2>Categorias ativas</h2><AsyncState loading={categories.isPending} error={categories.isError} empty={!categories.data?.items.length}><div className="list">{categories.data?.items.map((category) => <article className="list-row" key={category.id}><div><strong>{category.name}</strong><small>{category.kind === "expense" ? "Despesa" : "Receita"}</small></div><div className="button-row"><button className="text-button" onClick={() => { setEditing(category); setName(category.name); }}>Renomear</button><button className="text-button danger-text" onClick={() => { if (window.confirm(`Arquivar ${category.name}? Registros históricos manterão o vínculo.`)) archive.mutate(category); }}>Arquivar</button></div></article>)}</div></AsyncState></section>
    </div>
    {editing && <div className="modal-backdrop"><section className="modal" role="dialog" aria-modal="true"><h2>Renomear categoria</h2><p>O novo nome aparecerá no histórico; snapshots liquidados permanecem preservados.</p><label className="field"><span>Novo nome</span><input value={name} onChange={(event) => setName(event.target.value)} /></label><div className="modal-actions"><button className="ghost" onClick={() => setEditing(null)}>Cancelar</button><button className="primary" onClick={() => rename.mutate(editing)}>Salvar</button></div></section></div>}
  </Page>;
}
