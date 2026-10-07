import { readFileSync } from 'node:fs'
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { ThemeColorPicker } from '../src/components/ThemeColorPicker'
import {
  buildPalette,
  contrastRatio,
  DEFAULT_THEME_COLOR,
  paletteVariables,
} from '../src/theme/palette'
import { parseThemeColor } from '../src/theme/themeColor'

const everyHue = Array.from({ length: 360 }, (_, hue) => hue)

describe('buildPalette', () => {
  it('keeps white button text readable for every colour', () => {
    for (const hue of everyHue) {
      const { brand } = buildPalette(hue)
      expect(
        contrastRatio('#ffffff', brand[600]),
        String(hue),
      ).toBeGreaterThanOrEqual(4.5)
      expect(
        contrastRatio('#ffffff', brand[700]),
        String(hue),
      ).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('keeps text on the soft selected chips readable', () => {
    for (const hue of everyHue) {
      const { brand } = buildPalette(hue)
      expect(
        contrastRatio(brand[700], brand[100]),
        String(hue),
      ).toBeGreaterThanOrEqual(4.5)
      expect(
        contrastRatio(brand[800], brand[100]),
        String(hue),
      ).toBeGreaterThanOrEqual(4.5)
      expect(
        contrastRatio(brand[800], brand[200]),
        String(hue),
      ).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('keeps body and muted text readable on tinted surfaces', () => {
    for (const hue of everyHue) {
      const { brand, tone } = buildPalette(hue)
      expect(
        contrastRatio(tone[900], '#ffffff'),
        String(hue),
      ).toBeGreaterThanOrEqual(12)
      expect(
        contrastRatio(tone[600], brand[100]),
        String(hue),
      ).toBeGreaterThanOrEqual(4.5)
      expect(
        contrastRatio(tone[500], brand[50]),
        String(hue),
      ).toBeGreaterThanOrEqual(4.5)
    }
  })

  it('matches the default colours written in index.css', () => {
    const css = readFileSync(
      new URL('../src/index.css', import.meta.url),
      'utf8',
    )
    const vars = paletteVariables(buildPalette(DEFAULT_THEME_COLOR))
    for (const [name, value] of Object.entries(vars)) {
      expect(css, name).toContain(`${name}: ${value};`)
    }
  })
})

describe('parseThemeColor', () => {
  it('reads a stored hue and rejects anything else', () => {
    expect(parseThemeColor('95')).toBe(95)
    expect(parseThemeColor('400')).toBe(40)
    expect(parseThemeColor('vàng')).toBeNull()
    expect(parseThemeColor('mono')).toBeNull()
    expect(parseThemeColor('')).toBeNull()
    expect(parseThemeColor(null)).toBeNull()
  })
})

describe('ThemeColorPicker', () => {
  it('shows only the colour bar, default blue', () => {
    const html = renderToStaticMarkup(<ThemeColorPicker />)
    expect(html).toContain('aria-label="Màu chủ đạo"')
    expect(html).toContain('aria-valuetext="Xanh dương"')
    expect(html).toContain('type="range"')
    expect(html).not.toContain('aria-pressed')
  })
})
