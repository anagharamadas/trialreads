"use client";

import { useEffect, useRef, useState } from "react";
import {
  api,
  type ChatMessage,
  type CurateProposal,
} from "@/lib/api";

/** Side panel that drives the shelf-curation agent: conversation + a proposal
 *  card with per-book selection and an accept flow that bulk-adds to the shelf. */
export function CurationChat({
  shelfId,
  onClose,
  onAccepted,
}: {
  shelfId: string;
  onClose: () => void;
  onAccepted: () => void;
}) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [proposal, setProposal] = useState<CurateProposal | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [lastSent, setLastSent] = useState<ChatMessage[] | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy, proposal]);

  async function sendHistory(history: ChatMessage[]) {
    setBusy(true);
    setError(null);
    setLastSent(history);
    try {
      const res = await api.shelves.curate(shelfId, history);
      setMessages([...history, { role: "assistant", content: res.reply }]);
      if (res.proposal && res.proposal.items.length) {
        // A newer proposal supersedes the previous card.
        setProposal(res.proposal);
        setSelected(new Set(res.proposal.items.map((_, i) => i)));
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  function send(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;
    setInput("");
    setProposal(null); // a new question supersedes any pending proposal
    sendHistory([...messages, { role: "user", content: text }]);
  }

  async function acceptSelected() {
    if (!proposal) return;
    const items = proposal.items
      .filter((_, i) => selected.has(i))
      .map((it, idx) => ({
        title: it.title,
        author: it.author || null,
        cover_url: it.cover_url,
        reason: it.reason || null,
        reading_order: idx + 1, // renumber over the selected subset
      }));
    if (items.length === 0) return;
    setBusy(true);
    setError(null);
    try {
      await api.shelves.bulkAdd(shelfId, items, "agent");
      onAccepted();
      onClose();
    } catch (e) {
      setError(String(e));
      setBusy(false);
    }
  }

  function toggle(i: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(i) ? next.delete(i) : next.add(i);
      return next;
    });
  }

  return (
    <div className="fixed inset-0 z-30 flex justify-end bg-ink/30" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-md flex-col bg-cream shadow-card"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-cream-300 px-5 py-4">
          <h2 className="text-lg font-serif text-ink">Build this shelf with AI</h2>
          <button onClick={onClose} className="text-ink-soft hover:text-ink">
            ✕
          </button>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
          {messages.length === 0 && !busy && (
            <p className="text-sm text-ink-soft">
              Tell me what you want to learn or achieve, and I&rsquo;ll build an
              ordered reading list. For example: &ldquo;I want to learn business
              concepts to start a consulting firm in India.&rdquo;
            </p>
          )}

          {messages.map((m, i) => (
            <div
              key={i}
              className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
            >
              <div
                className={
                  m.role === "user"
                    ? "max-w-[85%] rounded-2xl rounded-br-sm bg-accent px-4 py-2 text-sm text-white"
                    : "max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-bl-sm bg-white/70 px-4 py-2 text-sm text-ink shadow-card"
                }
              >
                {m.content}
              </div>
            </div>
          ))}

          {busy && <p className="text-sm text-ink-soft">Thinking… (this can take a moment)</p>}

          {error && (
            <div className="rounded-md border border-accent/40 bg-accent/5 p-3 text-sm text-accent">
              {error}
              {lastSent && !busy && (
                <button
                  onClick={() => sendHistory(lastSent)}
                  className="ml-2 underline"
                >
                  Retry
                </button>
              )}
            </div>
          )}

          {proposal && (
            <div className="rounded-lg border border-cream-300 bg-white/60 p-4 shadow-card">
              {proposal.overview && (
                <p className="mb-3 text-sm text-ink-soft">{proposal.overview}</p>
              )}
              <div className="space-y-2">
                {proposal.items.map((it, i) => (
                  <label
                    key={i}
                    className="flex cursor-pointer gap-3 rounded-md p-1.5 hover:bg-cream-200"
                  >
                    <input
                      type="checkbox"
                      checked={selected.has(i)}
                      onChange={() => toggle(i)}
                      className="mt-1"
                    />
                    <div className="h-16 w-11 flex-shrink-0 overflow-hidden rounded bg-cream-300">
                      {it.cover_url ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img
                          src={it.cover_url}
                          alt=""
                          className="h-full w-full object-cover"
                        />
                      ) : null}
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm text-ink">
                        <span className="text-ink-soft">{it.reading_order}.</span>{" "}
                        {it.title}
                      </p>
                      {it.author && (
                        <p className="text-xs text-ink-soft">{it.author}</p>
                      )}
                      {it.reason && (
                        <p className="mt-0.5 line-clamp-2 text-xs italic text-ink-soft">
                          {it.reason}
                        </p>
                      )}
                    </div>
                  </label>
                ))}
              </div>
              <div className="mt-4 flex gap-2">
                <button
                  onClick={acceptSelected}
                  disabled={busy || selected.size === 0}
                  className="rounded-md bg-accent px-3 py-1.5 text-sm text-white hover:bg-accent-hover disabled:opacity-60"
                >
                  Add {selected.size} to shelf
                </button>
                <button
                  onClick={() => setProposal(null)}
                  className="rounded-md border border-cream-300 px-3 py-1.5 text-sm text-ink hover:bg-cream-200"
                >
                  Keep chatting
                </button>
              </div>
            </div>
          )}

          <div ref={endRef} />
        </div>

        <form onSubmit={send} className="border-t border-cream-300 p-3">
          <div className="flex gap-2">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Describe your goal…"
              disabled={busy}
              className="flex-1 rounded-full border border-cream-300 bg-white px-4 py-2 text-sm outline-none focus:border-accent"
            />
            <button
              type="submit"
              disabled={busy || !input.trim()}
              className="rounded-full bg-accent px-4 py-2 text-sm text-white hover:bg-accent-hover disabled:opacity-60"
            >
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
