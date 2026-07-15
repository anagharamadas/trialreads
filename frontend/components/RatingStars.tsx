/** Amazon-style star rating: five stars, golden fill proportional to the
 *  rating (half/partial stars via a clipped overlay), with the count beside.
 *  Pure display — no links, no interaction. */
export function RatingStars({
  rating,
  count,
}: {
  rating: number;
  count?: number | null;
}) {
  const pct = (Math.max(0, Math.min(5, rating)) / 5) * 100;
  return (
    <span
      className="inline-flex items-center gap-1"
      title={`${rating.toFixed(1)} out of 5`}
      aria-label={`Rated ${rating.toFixed(1)} out of 5${
        count != null ? ` from ${count.toLocaleString()} ratings` : ""
      }`}
    >
      <span className="relative inline-block text-sm leading-none tracking-tight">
        {/* base: empty stars */}
        <span aria-hidden className="text-cream-300">
          ★★★★★
        </span>
        {/* overlay: golden stars clipped to the rating percentage */}
        <span
          aria-hidden
          className="absolute inset-y-0 left-0 overflow-hidden whitespace-nowrap text-amber-400"
          style={{ width: `${pct}%` }}
        >
          ★★★★★
        </span>
      </span>
      {count != null && (
        <span className="text-xs text-ink-soft">({count.toLocaleString()})</span>
      )}
    </span>
  );
}
