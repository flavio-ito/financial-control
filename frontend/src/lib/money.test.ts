import { describe, expect, it } from "vitest";
import { formatBrl, parseBrlToMinor } from "./money";

describe("parseBrlToMinor", () => {
  it.each([
    ["0", 0],
    ["1", 100],
    ["1,2", 120],
    ["R$ 1.234,56", 123456],
    ["90.071.992.547.409,91", 9007199254740991],
  ])("converte %s textualmente", (source, expected) => {
    expect(parseBrlToMinor(source)).toBe(expected);
  });

  it.each(["1.2,00", "1,234", "-1,00", "NaN", "90.071.992.547.409,92"])(
    "rejeita entrada inválida ou insegura: %s",
    (source) => expect(() => parseBrlToMinor(source)).toThrow(),
  );
});

describe("formatBrl", () => {
  it("formata sem ponto flutuante", () => expect(formatBrl(-123456)).toBe("-R$ 1.234,56"));
});

