import { describe, expect, it } from 'vitest'
import { mergeDocumentTables } from '../src/structure/tables'
import type { DocumentTable } from '../src/api/structure'

function table(
  id: string,
  pageNo: number,
  cells: DocumentTable['cells'],
  overrides: Partial<DocumentTable> = {},
): DocumentTable {
  return {
    id,
    pageNo,
    rows: Math.max(1, ...cells.map((cell) => cell.row + cell.rowSpan)),
    columns: 2,
    continued: false,
    continuedFrom: null,
    bbox: null,
    cells,
    ...overrides,
  }
}

describe('mergeDocumentTables', () => {
  it('merges linked fragments, removes repeated headers, and preserves cell pages', () => {
    const tables = mergeDocumentTables([
      table(
        't-1',
        1,
        [
          {
            row: 0,
            column: 0,
            rowSpan: 1,
            colSpan: 1,
            text: 'STT',
            header: true,
            pageNo: 1,
            bbox: null,
          },
          {
            row: 0,
            column: 1,
            rowSpan: 1,
            colSpan: 1,
            text: 'Nội dung',
            header: true,
            pageNo: 1,
            bbox: null,
          },
          {
            row: 1,
            column: 0,
            rowSpan: 1,
            colSpan: 1,
            text: '1',
            header: false,
            pageNo: 1,
            bbox: null,
          },
          {
            row: 1,
            column: 1,
            rowSpan: 1,
            colSpan: 1,
            text: 'Dòng đầu',
            header: false,
            pageNo: 1,
            bbox: null,
          },
        ],
        { continued: true },
      ),
      table(
        't-2',
        2,
        [
          {
            row: 0,
            column: 0,
            rowSpan: 1,
            colSpan: 1,
            text: 'STT',
            header: true,
            pageNo: 2,
            bbox: null,
          },
          {
            row: 0,
            column: 1,
            rowSpan: 1,
            colSpan: 1,
            text: 'Nội dung',
            header: true,
            pageNo: 2,
            bbox: null,
          },
          {
            row: 1,
            column: 0,
            rowSpan: 1,
            colSpan: 1,
            text: '2',
            header: false,
            pageNo: 2,
            bbox: null,
          },
          {
            row: 1,
            column: 1,
            rowSpan: 1,
            colSpan: 1,
            text: 'Dòng tiếp',
            header: false,
            pageNo: 2,
            bbox: null,
          },
        ],
        { continued: true, continuedFrom: 't-1' },
      ),
    ])

    expect(tables).toHaveLength(1)
    expect(tables[0]).toMatchObject({
      id: 't-1',
      pageStart: 1,
      pageEnd: 2,
      pageNos: [1, 2],
      fragmentIds: ['t-1', 't-2'],
    })
    expect(
      tables[0].cells.map((cell) => [cell.row, cell.text, cell.pageNo]),
    ).toEqual([
      [0, 'STT', 1],
      [0, 'Nội dung', 1],
      [1, '1', 1],
      [1, 'Dòng đầu', 1],
      [2, '2', 2],
      [2, 'Dòng tiếp', 2],
    ])
  })

  it('recognizes legacy fragments with sequential STT rows when metadata is missing', () => {
    const fragment = (id: string, pageNo: number, start: number) =>
      table(
        id,
        pageNo,
        [0, 1, 2].map((offset) => ({
          row: offset,
          column: 0,
          rowSpan: 1,
          colSpan: 1,
          text: String(start + offset).padStart(2, '0'),
          header: offset === 0,
          pageNo,
          bbox: null,
        })),
        { columns: 1 },
      )

    const tables = mergeDocumentTables([
      fragment('legacy-1', 1, 1),
      fragment('legacy-2', 2, 4),
    ])

    expect(tables).toHaveLength(1)
    expect(tables[0].fragmentIds).toEqual(['legacy-1', 'legacy-2'])
    expect(tables[0].cells.map((cell) => cell.text)).toEqual([
      '01',
      '02',
      '03',
      '04',
      '05',
      '06',
    ])
    expect(tables[0].cells.some((cell) => cell.header)).toBe(false)
  })
})
