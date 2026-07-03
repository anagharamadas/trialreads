import type { Book } from "@/lib/api";

const STYLES: Record<Book["status"], string> = {
  Finished: "bg-emerald-100 text-emerald-800",
  Reading: "bg-amber-100 text-amber-900",
  "Ready to Start": "bg-sky-100 text-sky-800",
  "Yet to Buy": "bg-cream-300 text-ink-soft",
};

export function StatusBadge({ status }: { status: Book["status"] }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-medium leading-none ${STYLES[status]}`}
    >
      {status}
    </span>
  );
}
