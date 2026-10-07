/*
 * Sinh bảng màu giao diện từ một sắc độ (hue) người dùng chọn trong Cài đặt.
 *
 * Tính trong không gian OKLCH để mọi màu có cùng độ sáng cảm nhận: cùng một
 * bậc (50…900) thì vàng hay xanh cũng sáng tối như nhau, chữ trắng trên nút
 * luôn đủ tương phản. Kết quả là hai thang giống Tailwind:
 *   - brand-50…900: màu chủ đạo (nút, logo, mục đang chọn, nền nhạt);
 *   - tone-50…900: xám ngả theo màu chủ đạo (chữ, viền, nền trang).
 */

/** Màu người dùng chọn là một sắc độ OKLCH (0–359); mặc định xanh dương #0071d0. */
export const DEFAULT_THEME_COLOR = 253

export const PALETTE_STEPS = [
  50, 100, 200, 300, 400, 500, 600, 700, 800, 900,
] as const

export type PaletteStep = (typeof PALETTE_STEPS)[number]

export type Palette = {
  brand: Record<PaletteStep, string>
  tone: Record<PaletteStep, string>
}

// [độ sáng L, độ rực C] cho từng bậc, theo thang blue và slate của Tailwind.
const BRAND: Record<PaletteStep, [number, number]> = {
  50: [0.975, 0.014],
  100: [0.94, 0.034],
  200: [0.89, 0.06],
  300: [0.81, 0.105],
  400: [0.71, 0.16],
  500: [0.62, 0.2],
  600: [0.55, 0.23],
  700: [0.48, 0.22],
  800: [0.41, 0.18],
  900: [0.33, 0.13],
}

const TONE: Record<PaletteStep, [number, number]> = {
  50: [0.985, 0.004],
  100: [0.967, 0.008],
  200: [0.925, 0.013],
  300: [0.87, 0.02],
  400: [0.7, 0.032],
  500: [0.53, 0.036],
  600: [0.44, 0.036],
  700: [0.37, 0.036],
  800: [0.28, 0.034],
  900: [0.21, 0.032],
}

/** Chữ trắng trên brand-600 phải đạt mức AA cho chữ thường. */
const MIN_CONTRAST = 4.5

type Rgb = [number, number, number]

function oklchToLinearRgb(l: number, c: number, hue: number): Rgb {
  const rad = (hue * Math.PI) / 180
  const a = c * Math.cos(rad)
  const b = c * Math.sin(rad)
  const l1 = (l + 0.3963377774 * a + 0.2158037573 * b) ** 3
  const m1 = (l - 0.1055613458 * a - 0.0638541728 * b) ** 3
  const s1 = (l - 0.0894841775 * a - 1.291485548 * b) ** 3
  return [
    4.0767416621 * l1 - 3.3077115913 * m1 + 0.2309699292 * s1,
    -1.2684380046 * l1 + 2.6097574011 * m1 - 0.3413193965 * s1,
    -0.0041960863 * l1 - 0.7034186147 * m1 + 1.707614701 * s1,
  ]
}

function inGamut(rgb: Rgb) {
  return rgb.every((v) => v >= -1e-4 && v <= 1 + 1e-4)
}

/** Giảm độ rực tới khi màu nằm trong sRGB, giữ nguyên độ sáng và sắc độ. */
function fitToSrgb(l: number, c: number, hue: number): Rgb {
  const direct = oklchToLinearRgb(l, c, hue)
  if (inGamut(direct)) return direct
  let low = 0
  let high = c
  for (let i = 0; i < 20; i += 1) {
    const mid = (low + high) / 2
    if (inGamut(oklchToLinearRgb(l, mid, hue))) low = mid
    else high = mid
  }
  return oklchToLinearRgb(l, low, hue)
}

function toHex(rgb: Rgb) {
  return `#${rgb
    .map((v) => {
      const clamped = Math.min(1, Math.max(0, v))
      const srgb =
        clamped <= 0.0031308
          ? 12.92 * clamped
          : 1.055 * clamped ** (1 / 2.4) - 0.055
      return Math.round(srgb * 255)
        .toString(16)
        .padStart(2, '0')
    })
    .join('')}`
}

function luminance(hex: string) {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const v = parseInt(hex.slice(i, i + 2), 16) / 255
    return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4
  })
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

/** Tỉ lệ tương phản WCAG giữa hai màu hex. */
export function contrastRatio(a: string, b: string) {
  const [light, dark] = [luminance(a), luminance(b)].sort((x, y) => y - x)
  return (light + 0.05) / (dark + 0.05)
}

/** 1 ở giữa dải vàng (95°), về 0 ở cam (60°) và xanh nõn chuối (130°). */
function yellowness(hue: number) {
  return Math.max(0, 1 - Math.abs(hue - 95) / 35)
}

/*
 * Dải vàng cần xử lý riêng, như thang màu của Tailwind:
 *   - bậc đậm sẫm lại thành ô liu, nên xoay dần về phía cam để ra vàng đồng;
 *   - bậc nhạt ở độ rực chung trông như màu be, nên tăng độ rực cho ra vàng kem.
 */
function color(l: number, c: number, hue: number) {
  const weight = yellowness(hue)
  const darkness = Math.min(1, Math.max(0, (0.8 - l) / 0.25))
  const h = hue - 28 * weight * darkness
  const chroma = l >= 0.8 ? c * (1 + 2 * weight) : c
  return toHex(fitToSrgb(l, chroma, h))
}

/**
 * Màu cho thanh chọn: lấy độ sáng mà sắc độ đó rực nhất (vàng sáng, xanh dương
 * đậm), để thanh trông như cầu vồng quen thuộc.
 */
export function swatchColor(hue: number) {
  let bestL = 0.6
  let bestChroma = -1
  for (let l = 0.45; l <= 0.97; l += 0.02) {
    const [, a, b] = linearRgbToOklab(fitToSrgb(l, 0.4, hue))
    const chroma = Math.hypot(a, b)
    if (chroma > bestChroma) {
      bestChroma = chroma
      bestL = l
    }
  }
  // Bớt 20% độ rực cho đỡ chói.
  return toHex(fitToSrgb(bestL, bestChroma * 0.8, hue))
}

function linearRgbToOklab([r, g, b]: Rgb): Rgb {
  const l = Math.cbrt(0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b)
  const m = Math.cbrt(0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b)
  const s = Math.cbrt(0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b)
  return [
    0.2104542553 * l + 0.793617785 * m - 0.0040720468 * s,
    1.9779984951 * l - 2.428592205 * m + 0.4505937099 * s,
    0.0259040371 * l + 0.7827717662 * m - 0.808675766 * s,
  ]
}

export function normalizeHue(hue: number) {
  return ((Math.round(hue) % 360) + 360) % 360
}

export function buildPalette(choice: number): Palette {
  const hue = normalizeHue(choice)
  const brand = {} as Record<PaletteStep, string>
  const tone = {} as Record<PaletteStep, string>

  for (const step of PALETTE_STEPS) {
    const [l, c] = BRAND[step]
    brand[step] = color(l, c, hue)
    const [toneL, toneC] = TONE[step]
    tone[step] = color(toneL, toneC, hue)
  }

  // Vài sắc độ (xanh lá, xanh ngọc) ở L 0.55 vẫn quá sáng cho chữ trắng: hạ dần.
  let l = BRAND[600][0]
  while (contrastRatio('#ffffff', brand[600]) < MIN_CONTRAST && l > 0.3) {
    l -= 0.01
    brand[600] = color(l, BRAND[600][1], hue)
    brand[700] = color(l - 0.07, BRAND[700][1], hue)
  }

  return { brand, tone }
}

/** Biến CSS ghi đè `--color-brand-*` và `--color-tone-*` trong index.css. */
export function paletteVariables(palette: Palette): Record<string, string> {
  const vars: Record<string, string> = {}
  for (const step of PALETTE_STEPS) {
    vars[`--color-brand-${step}`] = palette.brand[step]
    vars[`--color-tone-${step}`] = palette.tone[step]
  }
  return vars
}
