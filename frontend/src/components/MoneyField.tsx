import type { FieldError, UseFormRegisterReturn } from "react-hook-form";

export function MoneyField({ label, registration, error }: { label: string; registration: UseFormRegisterReturn; error?: FieldError }) {
  const id = registration.name;
  return (
    <label className="field" htmlFor={id}>
      <span>{label}</span>
      <div className="money-control"><span>R$</span><input id={id} inputMode="decimal" placeholder="0,00" aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined} {...registration} /></div>
      {error && <small className="field-error" id={`${id}-error`}>{error.message}</small>}
    </label>
  );
}

