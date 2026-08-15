import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'

/**
 * Which theme the app is painted in, for the parts that CANNOT read CSS.
 *
 * CSS handles itself: light lives on bare `:root`, dark under
 * `prefers-color-scheme` AND `[data-theme="dark"]`. This context exists for
 * Recharts, which takes literal color strings and cannot resolve a custom
 * property — see charts/palette.js.
 *
 * Three states, not two: 'system' means no stamp on <html>, so the media query
 * decides and the app follows the OS as it changes. Toggling always writes an
 * explicit choice, which then wins in both directions.
 */

const KEY = 'airport-agent.theme'
const DARK_QUERY = '(prefers-color-scheme: dark)'

const ThemeContext = createContext({ theme: 'light', choice: 'system', toggle: () => {} })

function storedChoice() {
  try {
    const saved = window.localStorage.getItem(KEY)
    return saved === 'light' || saved === 'dark' ? saved : 'system'
  } catch {
    // Private mode, or a test environment without storage. Not worth failing over.
    return 'system'
  }
}

const systemPrefersDark = () => Boolean(window.matchMedia?.(DARK_QUERY).matches)

export function ThemeProvider({ children }) {
  const [choice, setChoice] = useState(storedChoice)
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  // Only meaningful while choice is 'system', but subscribing unconditionally
  // keeps the value correct the moment the user switches back to it.
  useEffect(() => {
    const media = window.matchMedia?.(DARK_QUERY)
    if (!media) return undefined
    const onChange = (event) => setSystemDark(event.matches)
    media.addEventListener('change', onChange)
    return () => media.removeEventListener('change', onChange)
  }, [])

  const theme = choice === 'system' ? (systemDark ? 'dark' : 'light') : choice

  // The stamp is what lets an explicit light choice beat an OS set to dark.
  // 'system' removes it so the media query is back in charge.
  useEffect(() => {
    const root = document.documentElement
    if (choice === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', choice)
    root.style.colorScheme = theme
  }, [choice, theme])

  const toggle = useCallback(() => {
    setChoice((prior) => {
      const resolved = prior === 'system' ? (systemPrefersDark() ? 'dark' : 'light') : prior
      const next = resolved === 'dark' ? 'light' : 'dark'
      try { window.localStorage.setItem(KEY, next) } catch { /* see storedChoice */ }
      return next
    })
  }, [])

  const value = useMemo(() => ({ theme, choice, toggle }), [theme, choice, toggle])
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

/** Defaults to light outside a provider, so a chart rendered in isolation still draws. */
export function useTheme() {
  return useContext(ThemeContext)
}
