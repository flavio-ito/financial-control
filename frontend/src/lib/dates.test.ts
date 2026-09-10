import { describe, expect, it } from "vitest";
import { formatDateBr, formatMonthBr } from "./dates";

describe("formatação pt-BR de datas", () => {
  it("formata datas ISO sem alterar o dia por fuso horário", () => {
    expect(formatDateBr("2026-09-09")).toBe("09/09/2026");
    expect(formatDateBr("2024-02-29T23:00:00Z")).toBe("29/02/2024");
    expect(formatMonthBr("2026-10")).toBe("10/2026");
  });
});
