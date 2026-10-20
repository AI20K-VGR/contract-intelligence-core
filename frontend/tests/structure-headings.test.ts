import { describe, expect, it } from 'vitest'
import {
  buildFreeformTree,
  buildNumberedTree,
  parseMarker,
} from '../src/structure'
import type { ClauseNode, OcrLine } from '../src/structure/types'

function page(pageNo: number, texts: string[]): OcrLine[] {
  return texts.map((text, index) => ({
    id: `p${pageNo}-l${index + 1}`,
    pageNo,
    lineNo: index + 1,
    text,
    bbox: null,
    pageWidth: 595,
    pageHeight: 842,
  }))
}

const ROW =
  '| 1 | Hạng mục 1: Cung cấp vật tư | gói | 2 | 1.230.000 | 2.460.000 |'

// Same lines as the OCR of the HD02 test contract: article titles start with
// "Điều khoản", and the annex heading lost its diacritics on page 2.
const HD02: OcrLine[] = [
  ...page(1, [
    'HỢP ĐỒNG DỊCH VỤ',
    'Số: 02/2026/HD-DV/MH-TT',
    'Căn cứ Bộ luật Dân sự và nhu cầu hợp tác của các bên, hôm nay chúng tôi gồm có:',
    'Bên A: CÔNG TY TNHH MINH HÒA. Mã số thuế: 0101234567.',
    'Điều 1. Nội dung 1',
    'Bên B cung cấp cho Bên A dịch vụ số hóa và hỗ trợ rà soát hồ sơ.',
    'Điều 2. Điều khoản 2',
    'Phạm vi bao gồm đọc PDF scan và nhận diện điều khoản.',
    'Điều 3. Điều khoản 3',
    'Tiến độ thực hiện gồm 03 giai đoạn.',
    'Điều 4. Điều khoản 4',
    'Bên A có trách nhiệm cung cấp hồ sơ.',
    'Điều 5. Điều khoản 5',
    'Mọi thay đổi ngoài phạm vi phải được lập phụ lục.',
  ]),
  ...page(2, ['PHU LUC 01 - BẢNG KHỐI LƯỢNG VÀ ĐƠN GIÁ', ROW]),
]

function flatten(nodes: ClauseNode[]): ClauseNode[] {
  return nodes.flatMap((node) => [node, ...flatten(node.children)])
}

function articles(nodes: ClauseNode[]) {
  return flatten(nodes).filter((node) => /^Điều \d/.test(node.label))
}

describe('parseMarker', () => {
  it('reads "Điều 2. Điều khoản 2" as an article heading', () => {
    expect(parseMarker('Điều 2. Điều khoản 2')).toMatchObject({
      kind: 'article',
      number: '2',
      rest: 'Điều khoản 2',
    })
    expect(parseMarker('Điều 7: Điều kiện thanh toán')).toMatchObject({
      kind: 'article',
      number: '7',
    })
  })

  it('still treats an unpunctuated "Khoản 2 Điều 5" as a cross-reference', () => {
    expect(
      parseMarker('Khoản 2 Điều 5 của Hợp đồng được sửa như sau'),
    ).toBeNull()
    expect(parseMarker('Điều 3 Khoản 1 quy định thời hạn')).toBeNull()
    expect(parseMarker('Điều 3 của Hợp đồng này')).toBeNull()
  })

  it('reads an annex heading whose diacritics OCR dropped', () => {
    expect(parseMarker('PHU LUC 01 - BẢNG KHỐI LƯỢNG')).toMatchObject({
      kind: 'annex',
      number: '01',
    })
    expect(parseMarker('Phụ lục 02')).toMatchObject({ kind: 'annex' })
  })
})

describe('buildNumberedTree on HD02', () => {
  const tree = buildNumberedTree(HD02)

  it('opens one node per article', () => {
    expect(articles(tree).map((node) => node.label)).toEqual([
      'Điều 1.',
      'Điều 2.',
      'Điều 3.',
      'Điều 4.',
      'Điều 5.',
    ])
  })

  it('keeps each article to its own text', () => {
    const [, second, third] = articles(tree)
    expect(second.text).toContain('Phạm vi bao gồm')
    expect(second.text).not.toContain('Tiến độ')
    expect(third.text).toContain('Tiến độ')
  })

  it('closes the last article at the annex', () => {
    const last = articles(tree)[4]
    expect(last.text).not.toContain('Hạng mục')
    expect(flatten(tree).some((node) => node.nodeType === 'annex')).toBe(true)
  })
})

describe('buildFreeformTree on HD02', () => {
  const tree = buildFreeformTree(HD02)

  it('makes every article a heading, all at one level', () => {
    const found = articles(tree)
    expect(found.map((node) => node.label)).toEqual([
      'Điều 1. Nội dung 1',
      'Điều 2. Điều khoản 2',
      'Điều 3. Điều khoản 3',
      'Điều 4. Điều khoản 4',
      'Điều 5. Điều khoản 5',
    ])
    expect(new Set(found.map((node) => node.level)).size).toBe(1)
  })

  it('does not turn the document number into a section above the articles', () => {
    const all = flatten(tree)
    expect(all.some((node) => node.label.startsWith('Số:'))).toBe(false)
    const holder = all.find((node) =>
      node.children.some((child) => child.label.startsWith('Điều 1')),
    )
    expect(holder?.label ?? 'root').not.toMatch(/^Số/)
  })
})
