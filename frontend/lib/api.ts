import { supabase } from "./supabaseClient";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type Book = {
  id: number;
  book: string;
  author: string | null;
  status: "Yet to Buy" | "Reading" | "Ready to Start" | "Finished";
  year: number | null;
  cover_url: string | null;
};

export type Recommendation = {
  title: string;
  author: string;
  reason: string;
  amazon_link: string;
};

async function authHeaders(): Promise<Record<string, string>> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
      ...(init.headers ?? {}),
    },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* non-JSON error */
    }
    throw new Error(`${res.status}: ${detail}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // Library CRUD
  listBooks: () => request<Book[]>("/library"),
  addBook: (b: Partial<Book>) =>
    request<Book>("/library", { method: "POST", body: JSON.stringify(b) }),
  updateBook: (id: number, b: Partial<Book>) =>
    request<Book>(`/library/${id}`, { method: "PUT", body: JSON.stringify(b) }),
  deleteBook: (id: number) =>
    request<void>(`/library/${id}`, { method: "DELETE" }),

  // AI
  summarise: (book_name: string, author_name = "") =>
    request<{ summary: string }>("/summarise", {
      method: "POST",
      body: JSON.stringify({ book_name, author_name }),
    }),
  recommend: (book_name: string, author_name = "") =>
    request<{ original_response: string; recommendations: Recommendation[] }>(
      "/recommend",
      { method: "POST", body: JSON.stringify({ book_name, author_name }) }
    ),
  queryLibrary: (query: string) =>
    request<{ answer: string; sql: string | null }>("/library/query", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),
};
