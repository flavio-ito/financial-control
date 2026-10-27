import { describe, expect, it } from "vitest";
import { transactionDirection } from "./transactions";

describe("transactionDirection", () => {
  it.each([
    ["income", 1000, "Entrada"],
    ["transfer_in", 1000, "Entrada"],
    ["refund", 1000, "Entrada"],
    ["expense", -1000, "Despesa"],
    ["card_purchase", -1000, "Despesa"],
    ["transfer_out", -1000, "Despesa"],
  ])("classifica %s", (kind, amount, expected) => {
    expect(transactionDirection(kind, amount)).toBe(expected);
  });

  it("usa o sinal para tipos sem direção fixa", () => {
    expect(transactionDirection("balance_adjustment", 1000)).toBe("Entrada");
    expect(transactionDirection("balance_adjustment", -1000)).toBe("Despesa");
  });
});
