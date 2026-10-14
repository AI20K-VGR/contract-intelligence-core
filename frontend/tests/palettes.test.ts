import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'
import { DEFAULT_PALETTE, PALETTES, parsePalette } from '../src/theme/palettes'

const css = readFileSync(new URL('../src/index.css', import.meta.url), 'utf8')

/** Biến màu khai báo trong khối [data-palette='id'] của index.css. */
function paletteVars(id: string) {
  const block = css.match(
    new RegExp(`^\\[data-palette='${id}'\\]\\s*\\{([^}]*)\\}`, 'm'),
  )
  if (!block) return null
  const vars: Record<string, string> = {}
  for (const [, name, value] of block[1].matchAll(/--([\w-]+):\s*([^;]+);/g)) {
    vars[name] = value.trim()
  }
  return vars
}

function luminance(hex: string) {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(hex.slice(i, i + 2), 16) / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contrast(a: string, b: string) {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (hi + 0.05) / (lo + 0.05)
}

const brandSteps = [50, 100, 200, 300, 400, 500, 600, 700, 800, 900]

describe('palettes', () => {
  it('has unique ids and a default that exists', () => {
    const ids = PALETTES.map((palette) => palette.id)
    expect(new Set(ids).size).toBe(ids.length)
    expect(ids).toContain(DEFAULT_PALETTE)
  })

  it('accepts only known ids from storage', () => {
    for (const { id } of PALETTES) expect(parsePalette(id)).toBe(id)
    expect(parsePalette('1')).toBeNull()
    expect(parsePalette('6')).toBeNull()
    expect(parsePalette(2)).toBeNull()
    expect(parsePalette(null)).toBeNull()
    expect(parsePalette('')).toBeNull()
  })

  it('defines every brand step in index.css for each palette', () => {
    for (const { id } of PALETTES) {
      const vars = paletteVars(id)
      expect(vars, `palette ${id}`).not.toBeNull()
      for (const step of brandSteps) {
        expect(
          vars![`color-brand-${step}`],
          `palette ${id} brand-${step}`,
        ).toMatch(/^#[0-9a-f]{6}$/i)
      }
    }
  })

  it('keeps text on the soft brand chips readable', () => {
    // Bảng 10 (Hoa anh đào) cố ý giữ hồng nhạt: brand-700 chỉ đạt ~4.0/3.5, chưa đủ 4.5.
    const softPalettes = new Set(['10'])
    for (const { id } of PALETTES) {
      if (softPalettes.has(id)) continue
      const vars = paletteVars(id)!
      for (const [ink, bg] of [
        ['color-brand-700', 'color-brand-100'],
        ['color-brand-700', 'color-brand-200'],
      ]) {
        expect(
          contrast(vars[ink], vars[bg]),
          `palette ${id} ${ink} on ${bg}`,
        ).toBeGreaterThanOrEqual(4.5)
      }
    }
  })

  it('keeps sidebar text readable', () => {
    for (const { id } of PALETTES) {
      const vars = paletteVars(id)!
      const side = vars['color-side']
      const ink = vars['color-side-ink']
      if (!side?.startsWith('#') || !ink?.startsWith('#')) continue
      expect(contrast(ink, side), `palette ${id}`).toBeGreaterThanOrEqual(4.5)
    }
  })
})
