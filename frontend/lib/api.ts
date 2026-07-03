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

export type Shelf = {
  id: string;
  name: string;
  description: string | null;
  book_count: number;
  created_at?: string | null;
};

export type ShelfBook = {
  id: string;
  shelf_id: string;
  library_book_id: number | null;
  title: string;
  author: string | null;
  cover_url: string | null;
  reason: string | null;
  reading_order: number | null;
  added_by: "user" | "agent";
};

export type ShelfBookInput = {
  title: string;
  author?: string | null;
  cover_url?: string | null;
  reason?: string | null;
  reading_order?: number | null;
  library_book_id?: number | null;
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

  // Covers (Google Books via backend)
  getCover: (title: string, author = "") =>
    request<{ cover_url: string | null }>(
      `/covers?title=${encodeURIComponent(title)}&author=${encodeURIComponent(author)}`
    ),

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

  // Shelves (Phase 2)
  shelves: {
    list: () => request<Shelf[]>("/shelves"),
    create: (b: { name: string; description?: string | null }) =>
      request<Shelf>("/shelves", { method: "POST", body: JSON.stringify(b) }),
    update: (id: string, b: { name?: string; description?: string | null }) =>
      request<Shelf>(`/shelves/${id}`, { method: "PUT", body: JSON.stringify(b) }),
    remove: (id: string) =>
      request<void>(`/shelves/${id}`, { method: "DELETE" }),
    books: (id: string) => request<ShelfBook[]>(`/shelves/${id}/books`),
    addBook: (id: string, b: ShelfBookInput) =>
      request<ShelfBook>(`/shelves/${id}/books`, {
        method: "POST",
        body: JSON.stringify(b),
      }),
    bulkAdd: (id: string, items: ShelfBookInput[], added_by: "user" | "agent" = "agent") =>
      request<ShelfBook[]>(`/shelves/${id}/books/bulk`, {
        method: "POST",
        body: JSON.stringify({ items, added_by }),
      }),
    updateBook: (id: string, bookId: string, b: Partial<ShelfBookInput>) =>
      request<ShelfBook>(`/shelves/${id}/books/${bookId}`, {
        method: "PUT",
        body: JSON.stringify(b),
      }),
    removeBook: (id: string, bookId: string) =>
      request<void>(`/shelves/${id}/books/${bookId}`, { method: "DELETE" }),
  },
};
