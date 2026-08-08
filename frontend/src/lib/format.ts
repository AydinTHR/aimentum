/** "3" not "3.00", "2.5" not "2.50": numbers read like a person wrote them. */
export function formatNumber(value: number): string {
  if (Number.isInteger(value)) return String(value);
  return String(Math.round(value * 100) / 100);
}
