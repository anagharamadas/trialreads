"use client";

import type { Book } from "@/lib/api";

export type Filters = {
  status: string; // "" = all
  author: string; // "" = all
  year: string; // "" = all (kept as string for the <select>)
};

export const EMPTY_FILTERS: Filters = { status: "", author: "", year: "" };

const STATUSES: Book["status"][] = [
  "Reading",
  "Finished",
  "Yet to Buy",
  "Ready to Start",
];

const selectBase =
  "rounded-full border bg-white px-3 py-1.5 text-sm text-ink outline-none focus:border-accent";

function FilterSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
}) {
  const active = value !== "";
  return (
    <select
      aria-label={label}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`${selectBase} ${
        active
          ? "border-accent bg-accent/5 font-medium text-accent"
          : "border-cream-300"
      }`}
    >
      <option value="">{label}: All</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

/** Filter bar for the Library shelf. Pure client-side; options derived from the
 *  already-loaded books. Sits above the cover grid without altering it. */
export function FilterBar({
  books,
  filters,
  onChange,
}: {
  books: Book[];
  filters: Filters;
  onChange: (f: Filters) => void;
}) {
  const authors = Array.from(
    new Set(books.map((b) => b.author?.trim()).filter((a): a is string => !!a))
  ).sort((a, b) => a.localeCompare(b));

  const years = Array.from(
    new Set(books.map((b) => b.year).filter((y): y is number => y != null))
  )
    .sort((a, b) => b - a)
    .map(String);

  const anyActive =
    filters.status !== "" || filters.author !== "" || filters.year !== "";

  return (
    <div className="mb-6 flex flex-wrap items-center gap-2">
      <FilterSelect
        label="Status"
        value={filters.status}
        options={STATUSES}
        onChange={(status) => onChange({ ...filters, status })}
      />
      <FilterSelect
        label="Author"
        value={filters.author}
        options={authors}
        onChange={(author) => onChange({ ...filters, author })}
      />
      <FilterSelect
        label="Year"
        value={filters.year}
        options={years}
        onChange={(year) => onChange({ ...filters, year })}
      />
      {anyActive && (
        <button
          onClick={() => onChange(EMPTY_FILTERS)}
          className="rounded-full px-3 py-1.5 text-sm text-accent hover:bg-accent/5 hover:underline"
        >
          Clear all
        </button>
      )}
    </div>
  );
}

/** AND-combine the active filters. */
export function applyFilters(books: Book[], f: Filters): Book[] {
  return books.filter(
    (b) =>
      (f.status === "" || b.status === f.status) &&
      (f.author === "" || (b.author ?? "").trim() === f.author) &&
      (f.year === "" || String(b.year ?? "") === f.year)
  );
}
