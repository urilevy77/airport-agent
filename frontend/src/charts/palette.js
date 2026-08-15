import { useMemo } from 'react'
import { useTheme } from '../theme/ThemeContext'

/**
 * Chart colors as literal hex, per theme.
 *
 * Recharts takes color strings, not CSS custom properties, so the chart layer
 * cannot inherit the token swap in theme.css — it has to be handed the right
 * values. These MIRROR the tokens there; change one, change both.
 *
 * The two series hues were run through the data-viz validator against the real
 * card surfaces (#ffffff light, #17181c dark) and pass every gate in both
 * modes: lightness band, chroma floor, CVD separation (worst adjacent ΔE 24.7
 * light / 26.8 dark), normal-vision floor and 3:1 contrast.
 *
 * Status colors are RESERVED — they mean a state (a HIGH load factor, a
 * pre-pandemic shortfall), never "series 3". They always ship with a written
 * label beside them, so the color never carries the meaning alone.
 */

const STATUS = {
  good: '#0ca30c',
  warning: '#fab219',
  serious: '#ec835a',
  critical: '#d03b3b',
}

export const PALETTES = {
  light: {
    series: ['#2a78d6', '#eb6834'],
    accent: '#2a78d6',
    surface: '#ffffff',
    grid: '#e8e8e3',
    axisLine: '#d3d3cc',
    axisText: '#6c6e75',
    reference: '#86888f',
    ...STATUS,
  },
  dark: {
    series: ['#3987e5', '#d95926'],
    accent: '#3987e5',
    surface: '#17181c',
    grid: '#26282d',
    axisLine: '#3a3d44',
    axisText: '#9a9da4',
    reference: '#8a8d94',
    ...STATUS,
  },
}

export const MONO = "'IBM Plex Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

/**
 * The palette for the active theme, plus the derived props charts pass around
 * (tick styling, tooltip chrome) so no chart re-invents them.
 */
export function useChartPalette() {
  const { theme } = useTheme()
  return useMemo(() => {
    const p = PALETTES[theme] || PALETTES.light
    return {
      ...p,
      // Axis text is ink, never a series color — a label wearing the data color
      // is illegible at these weights and confuses identity with value.
      tick: { fontSize: 11, fill: p.axisText, fontFamily: MONO },
      tooltip: {
        contentStyle: {
          background: p.surface,
          border: `1px solid ${p.axisLine}`,
          borderRadius: 8,
          fontSize: 12,
          boxShadow: '0 4px 16px rgba(0,0,0,0.10)',
        },
        labelStyle: { color: p.axisText, fontFamily: MONO, fontSize: 11 },
        itemStyle: { color: p.axisText },
        cursor: { fill: p.grid, fillOpacity: 0.45 },
      },
    }
  }, [theme])
}
