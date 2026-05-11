import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { ArrowRight, FileSearch } from 'lucide-react'
import { useAuthStore } from '@/store/authStore'
import LanguageSwitcher from '@/components/layout/LanguageSwitcher'
import ThemeToggle from '@/components/layout/ThemeToggle'
import api from '@/lib/api'

function isValidEmail(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)
}

export default function LoginPage() {
  const { t } = useTranslation('auth')
  const navigate = useNavigate()
  const setAuth = useAuthStore((s) => s.setAuth)
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const docTypes = t('docTypes', { returnObjects: true }) as string[]

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!isValidEmail(email)) {
      setError(t('invalidEmail'))
      return
    }
    setError('')
    setLoading(true)
    try {
      const res = await api.post('/auth/login', { email })
      const { access_token } = res.data
      localStorage.setItem('auth_token', access_token)
      setAuth(access_token, email)
      navigate('/dashboard')
    } catch {
      setError(t('loginError'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-background">
      {/* Left panel — brand */}
      <div className="hidden lg:flex lg:w-[46%] flex-col justify-between p-12 bg-[var(--surface-sunken)] border-r border-border relative overflow-hidden">
        {/* Background texture */}
        <div
          className="absolute inset-0 opacity-[0.03]"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, var(--foreground) 1px, transparent 0)`,
            backgroundSize: '28px 28px',
          }}
        />

        {/* Decorative circles */}
        <div
          className="absolute -bottom-32 -left-32 w-[520px] h-[520px] rounded-full opacity-[0.04]"
          style={{ background: 'var(--primary)' }}
        />
        <div
          className="absolute -bottom-16 -left-16 w-[360px] h-[360px] rounded-full opacity-[0.06]"
          style={{ background: 'var(--primary)' }}
        />

        {/* Logo */}
        <div className="relative z-10 flex items-center gap-3">
          <div className="size-8 rounded-lg flex items-center justify-center bg-primary text-primary-foreground">
            <FileSearch className="h-4 w-4" />
          </div>
          <span className="font-display text-xl text-foreground">HRRag</span>
        </div>

        {/* Tagline */}
        <div className="relative z-10 space-y-4">
          <p className="font-display text-4xl leading-tight text-foreground">
            {t('tagline').split('\n').map((line) =>
              line === t('tagline').split('\n')[1]
                ? <span key="highlight"><br /><em className="text-primary not-italic">{line}</em></span>
                : <span key="main">{line}</span>
            )}
          </p>
          <p className="text-sm text-muted-foreground leading-relaxed max-w-xs">
            {t('taglineDesc')}
          </p>
        </div>

        {/* Doc type badges */}
        <div className="relative z-10 flex flex-wrap gap-2">
          {Array.isArray(docTypes) && docTypes.map((label) => (
            <span
              key={label}
              className="px-2.5 py-1 rounded-full text-xs border border-border text-muted-foreground bg-background/60"
            >
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* Right panel — form */}
      <div className="flex-1 flex flex-col items-center justify-center p-8 relative">
        {/* Top-right controls */}
        <div className="absolute top-4 right-4 flex items-center gap-1">
          <LanguageSwitcher />
          <ThemeToggle />
        </div>

        {/* Mobile logo */}
        <div className="lg:hidden mb-10 flex items-center gap-2">
          <div className="size-7 rounded-lg flex items-center justify-center bg-primary text-primary-foreground">
            <FileSearch className="h-3.5 w-3.5" />
          </div>
          <span className="font-display text-lg text-foreground">HRRag</span>
        </div>

        <div className="w-full max-w-[340px] space-y-8">
          <div>
            <h1 className="text-2xl font-semibold text-foreground tracking-tight">{t('title')}</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">{t('subtitle')}</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-1.5">
              <label htmlFor="email" className="text-sm font-medium text-foreground">
                {t('emailLabel')}
              </label>
              <input
                id="email"
                type="email"
                placeholder={t('emailPlaceholder')}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full h-10 px-3.5 rounded-lg border border-input bg-background text-sm text-foreground
                  placeholder:text-muted-foreground/60
                  focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent
                  transition-all duration-150"
              />
            </div>

            {error && (
              <p className="text-sm text-destructive fade-up">{error}</p>
            )}

            <button
              type="submit"
              disabled={loading || !email.trim()}
              className="w-full h-10 px-4 rounded-lg bg-primary text-primary-foreground text-sm font-medium
                flex items-center justify-center gap-2
                hover:opacity-90 active:scale-[0.98]
                disabled:opacity-50 disabled:cursor-not-allowed
                transition-all duration-150"
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-current dot-pulse-0" />
                  <span className="w-1.5 h-1.5 rounded-full bg-current dot-pulse-1" />
                  <span className="w-1.5 h-1.5 rounded-full bg-current dot-pulse-2" />
                </span>
              ) : (
                <>
                  {t('loginButton')}
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
