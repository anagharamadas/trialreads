# TrialReads Frontend

Next.js (TypeScript/React) frontend for TrialReads application.

## Overview

The frontend provides:
- **Chat Interface**: Real-time conversation with the ReAct agent
- **Library Management**: View, add, edit, delete books with a data grid UI
- **Book Summaries**: Display and interact with book summaries
- **Recommendations**: Browse and open Amazon links for recommended books
- **Responsive Design**: Works on desktop and mobile devices

## Architecture

```
app/
├── page.tsx              # Home / main page
├── layout.tsx            # Root layout
├── components/
│   ├── Chat/
│   │   ├── ChatWindow.tsx
│   │   ├── MessageList.tsx
│   │   └── ChatInput.tsx
│   ├── Library/
│   │   ├── LibraryGrid.tsx
│   │   ├── AddBookModal.tsx
│   │   └── EditBookModal.tsx
│   ├── Book/
│   │   ├── SummaryCard.tsx
│   │   └── RecommendationCard.tsx
│   └── common/
│       ├── Header.tsx
│       ├── Tabs.tsx
│       └── Loading.tsx
├── api/
│   └── client.ts         # API client (fetch/axios wrapper)
├── hooks/
│   ├── useChat.ts
│   ├── useLibrary.ts
│   └── useMessages.ts
├── types/
│   └── index.ts          # TypeScript types
├── styles/
│   └── globals.css       # Global styles
└── utils/
    └── helpers.ts        # Utility functions
```

## Stack

- **Framework**: Next.js 14+ with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS
- **UI Components**: shadcn/ui (or Headless UI)
- **State Management**: React Hooks + Context / TanStack Query (optional)
- **HTTP Client**: Fetch API or Axios

## Setup

1. **Install dependencies**:
   ```bash
   npm install
   ```

2. **Create .env.local file**:
   ```bash
   cp .env.example .env.local
   # Set NEXT_PUBLIC_API_URL=http://localhost:8000
   ```

3. **Run development server**:
   ```bash
   npm run dev
   ```

   Frontend will be available at `http://localhost:3000`

## Available Scripts

```bash
# Development (with hot reload)
npm run dev

# Build for production
npm run build

# Run production build locally
npm start

# Run linter (ESLint)
npm run lint

# Format code (Prettier)
npm run format
```

## Environment Variables

```env
# API
NEXT_PUBLIC_API_URL=http://localhost:8000

# Optional
NEXT_PUBLIC_APP_NAME=TrialReads
DEBUG=false
```

Note: Variables prefixed with `NEXT_PUBLIC_` are available in the browser.

## Features

### 1. Chat Tab (💬)
- Real-time chat with ReAct agent
- Message history
- Typing indicators
- Error handling

### 2. Library Tab (📚)
- Data grid view of all books
- Inline editing (Book, Author, Status, Year)
- Add new books (expandable rows)
- Delete books
- Save/Refresh buttons
- Validation (Book required, warnings for Finished without Year)

### 3. Book Summaries
- Display chapter-by-chapter summaries
- "Get Recommendations" button
- Amazon purchase links

### 4. Recommendations
- 5 book recommendations per query
- Title, Author, Reason displayed
- One-click Amazon search links

## Component Examples

### Chat Component
```tsx
<Chat />
  ├── ChatWindow
  │   ├── MessageList
  │   └── ChatInput
  └── (displays messages, handles input)
```

### Library Component
```tsx
<Library />
  ├── LibraryGrid (editable table)
  ├── AddBookModal
  ├── SaveButton
  └── RefreshButton
```

## API Integration

Example API client:

```ts
// api/client.ts
export const apiClient = {
  chat: {
    send: (message: string) => 
      fetch(`${API_URL}/api/chat`, { method: 'POST', body: JSON.stringify({ message }) }),
    history: () => 
      fetch(`${API_URL}/api/chat/history`)
  },
  library: {
    list: () => fetch(`${API_URL}/api/library`),
    add: (book) => fetch(`${API_URL}/api/library`, { method: 'POST', body: JSON.stringify(book) }),
    update: (id, book) => fetch(`${API_URL}/api/library/${id}`, { method: 'PUT', body: JSON.stringify(book) }),
    delete: (id) => fetch(`${API_URL}/api/library/${id}`, { method: 'DELETE' })
  }
}
```

## Styling

- **Tailwind CSS** for utility-first styling
- **shadcn/ui** for pre-built accessible components
- Custom theme in `globals.css`

## Testing

```bash
# Run tests (with Jest + React Testing Library)
npm run test

# Watch mode
npm run test:watch

# Coverage
npm run test:coverage
```

## Deployment

### Vercel (Recommended for Next.js)
1. Push to GitHub
2. Connect repo to Vercel
3. Set `NEXT_PUBLIC_API_URL` environment variable
4. Deploy

### Self-Hosted
1. Build: `npm run build`
2. Start: `npm start` (runs on port 3000 by default)
3. Use a reverse proxy (nginx) if needed

## Performance Considerations

- Images: Use `next/image` for optimization
- Code Splitting: Automatic per route
- API Caching: Use TanStack Query for request deduplication
- SEO: Use next/head for metadata

## Troubleshooting

### API Connection Issues
- Check `NEXT_PUBLIC_API_URL` in `.env.local`
- Ensure backend is running (`http://localhost:8000`)
- Check browser console for CORS errors

### Build Issues
- Clear `.next` folder: `rm -rf .next`
- Reinstall dependencies: `rm -rf node_modules && npm install`
- Check Node version: `node -v` (should be 18+)

## Contributing

- Follow TypeScript strict mode
- Use functional components and hooks
- Add PropTypes or TypeScript interfaces
- Test new features with React Testing Library
- Run `npm run lint` before committing
