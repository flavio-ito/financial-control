export const MAX_SAFE_MINOR = 9_007_199_254_740_991;

export function parseBrlToMinor(input: string): number {
  const normalized = input.trim().replace(/^R\$\s?/, "").replace(/\s/g, "");
  if (!/^(?:0|[1-9]\d{0,12})(?:\.\d{3})*(?:,\d{1,2})?$/.test(normalized)) {
    throw new Error("Informe um valor monetário válido, como 1.234,56.");
  }
  const [wholeWithSeparators, fraction = ""] = normalized.split(",");
  const whole = wholeWithSeparators?.replace(/\./g, "") ?? "0";
  const minorText = `${whole}${fraction.padEnd(2, "0")}`.replace(/^0+(?=\d)/, "");
  const minor = Number(minorText);
  if (!Number.isSafeInteger(minor) || minor > MAX_SAFE_MINOR) {
    throw new Error("O valor ultrapassa o limite monetário permitido.");
  }
  return minor;
}

export function formatBrl(minor: number): string {
  if (!Number.isSafeInteger(minor) || Math.abs(minor) > MAX_SAFE_MINOR) {
    throw new Error("Valor monetário fora do intervalo seguro.");
  }
  const sign = minor < 0 ? "-" : "";
  const digits = Math.abs(minor).toString().padStart(3, "0");
  const whole = digits.slice(0, -2).replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return `${sign}R$ ${whole},${digits.slice(-2)}`;
}

