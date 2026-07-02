/**
 * Format a raw value using a de_funk format code.
 *
 * Format codes:
 *   $        → $185.20
 *   $K       → $185.2K
 *   $M       → $1.85M
 *   %        → 4.6%  (input as 0.046)
 *   %2       → 4.56%
 *   number   → 1,234,567
 *   decimal  → 1.2346
 *   decimal2 → 1.23
 *   date     → 2024-01-02
 *   text     → unformatted
 */
export function formatValue(value: unknown, format: string | null | undefined): string {
  if (value === null || value === undefined) return "—";
  if (!format) return String(value);

  const n = Number(value);

  switch (format) {
    case "$":
      return isNaN(n) ? String(value) : `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    case "$K":
      return isNaN(n) ? String(value) : `$${(n / 1000).toLocaleString("en-US", { maximumFractionDigits: 1 })}K`;

    case "$M":
      return isNaN(n) ? String(value) : `$${(n / 1_000_000).toLocaleString("en-US", { maximumFractionDigits: 2 })}M`;

    case "$B":
      return isNaN(n) ? String(value) : `$${(n / 1_000_000_000).toLocaleString("en-US", { maximumFractionDigits: 2 })}B`;

    case "$2":
      return isNaN(n) ? String(value) : `$${n.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

    case "%":
      return isNaN(n) ? String(value) : `${(n * 100).toFixed(1)}%`;

    case "%2":
      return isNaN(n) ? String(value) : `${(n * 100).toFixed(2)}%`;

    case "number":
      return isNaN(n) ? String(value) : n.toLocaleString("en-US", { maximumFractionDigits: 0 });

    case "decimal":
      return isNaN(n) ? String(value) : n.toFixed(4);

    case "decimal2":
      return isNaN(n) ? String(value) : n.toFixed(2);

    case "date":
      if (typeof value === "number") {
        // Packed integer date: 20240102 → 2024-01-02
        const s = String(value);
        return `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}`;
      }
      return String(value);

    case "text":
    default:
      return String(value);
  }
}
