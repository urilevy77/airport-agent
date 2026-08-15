import { useTheme } from '../theme/ThemeContext'

/** Flips light/dark. The label names the destination, not the current state. */
export default function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const next = theme === 'dark' ? 'light' : 'dark'
  return (
    <button
      type="button"
      className="theme-toggle"
      onClick={toggle}
      title={`Switch to ${next} theme`}
      aria-label={`Switch to ${next} theme`}
    >
      {theme === 'dark' ? '☀' : '☾'}
    </button>
  )
}
