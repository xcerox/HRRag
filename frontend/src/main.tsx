import './i18n/config'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import App from './App'
import './index.css'

// Apply stored theme before render to avoid flash
const stored = localStorage.getItem('theme-storage')
if (stored) {
  try {
    const { state } = JSON.parse(stored)
    if (state?.theme === 'dark') {
      document.documentElement.classList.add('dark')
    }
  } catch {}
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
)
