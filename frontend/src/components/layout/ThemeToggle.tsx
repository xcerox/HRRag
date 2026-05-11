import { Sun, Moon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useThemeStore } from '@/store/themeStore'
import { useTranslation } from 'react-i18next'

export default function ThemeToggle() {
  const { t } = useTranslation('common')
  const { theme, toggleTheme } = useThemeStore()
  return (
    <Button variant="ghost" size="icon" onClick={toggleTheme} title={t('theme.toggle')}>
      {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </Button>
  )
}
