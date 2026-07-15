"use client";

import { useRef, useState } from "react";
import { RequireAuth } from "@/components/RequireAuth";
import { Header } from "@/components/Header";
import { api } from "@/lib/api";

type Msg = { role: "user" | "assistant"; text: string };

function Chat() {
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || busy) return;

    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setBusy(true);

    try {
      // "summarise <book>" → /summarise; anything else → library text-to-SQL.
      const m = text.match(/^summar(?:ise|ize)\s+(.+)/i);
      let reply: string;
      if (m) {
        reply = (await api.summarise(m[1])).summary;
      } else {
        // Prior turns give the backend chat memory: follow-ups like "which
        // ones?" are condensed into standalone questions server-side.
        const history = messages.map((msg) => ({
          role: msg.role,
          content: msg.text,
        }));
        reply = (await api.queryLibrary(text, history)).answer;
      }
      setMessages((msgs) => [...msgs, { role: "assistant", text: reply }]);
    } catch (err) {
      setMessages((msgs) => [
        ...msgs,
        { role: "assistant", text: `Error: ${String(err)}` },
      ]);
    } finally {
      setBusy(false);
      setTimeout(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
    }
  }

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto flex max-w-2xl flex-col px-6 py-10">
        <h1 className="text-3xl text-ink">Chat</h1>
        <p className="mt-2 text-sm text-ink-soft">
          Ask about your library — e.g.{" "}
          <em>&ldquo;how many books have I finished?&rdquo;</em> — or type{" "}
          <em>&ldquo;summarise Atomic Habits&rdquo;</em> for a chapter summary.
        </p>

        <div className="mt-6 space-y-4">
          {messages.length === 0 && (
            <p className="text-ink-soft">Ask your first question below.</p>
          )}
          {messages.map((m, i) => (
            <div
              key={i}
              className={m.role === "user" ? "flex justify-end" : "flex justify-start"}
            >
              <div
                className={
                  m.role === "user"
                    ? "max-w-[85%] rounded-2xl rounded-br-sm bg-accent px-4 py-2 text-white"
                    : "max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-bl-sm bg-white/70 px-4 py-2 text-ink shadow-card"
                }
              >
                {m.text}
              </div>
            </div>
          ))}
          {busy && <p className="text-sm text-ink-soft">Thinking…</p>}
          <div ref={endRef} />
        </div>

        <form onSubmit={send} className="sticky bottom-6 mt-6 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your library, or 'summarise <book>'…"
            className="flex-1 rounded-full border border-cream-300 bg-white px-4 py-2 outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={busy}
            className="rounded-full bg-accent px-5 py-2 text-white hover:bg-accent-hover disabled:opacity-60"
          >
            Send
          </button>
        </form>
      </main>
    </div>
  );
}

export default function Page() {
  return (
    <RequireAuth>
      <Chat />
    </RequireAuth>
  );
}
