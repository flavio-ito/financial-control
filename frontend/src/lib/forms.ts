import { z } from "zod";
import { parseBrlToMinor } from "./money";

export const requiredText = z.string().trim().min(1, "Campo obrigatório.");
export const moneyText = z.union([z.string(), z.number().int()]).transform((value, context) => {
  try {
    if (typeof value === "number") {
      if (!Number.isSafeInteger(value) || Math.abs(value) > Number.MAX_SAFE_INTEGER) throw new Error("Valor fora do intervalo seguro.");
      return value;
    }
    return parseBrlToMinor(value);
  }
  catch (error) { context.addIssue({ code: z.ZodIssueCode.custom, message: error instanceof Error ? error.message : "Valor inválido." }); return z.NEVER; }
});
export const todayIso = () => new Date().toLocaleDateString("sv-SE", { timeZone: "America/Sao_Paulo" });
export const yesterdayIso = () => new Date(Date.now() - 24 * 60 * 60 * 1000).toLocaleDateString("sv-SE", { timeZone: "America/Sao_Paulo" });
export const currentMonth = () => todayIso().slice(0, 7);
