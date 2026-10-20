import type { DocumentTable, DocumentTableCell } from '../api/structure'

export type MergedDocumentTable = DocumentTable & {
  pageStart: number
  pageEnd: number
  pageNos: number[]
  fragmentIds: string[]
}

function cellText(cell: DocumentTableCell) {
  return cell.text.trim().replace(/\s+/g, ' ').toLocaleLowerCase()
}

function rowSignature(table: DocumentTable, row: number) {
  return table.cells
    .filter((cell) => cell.row === row)
    .sort((a, b) => a.column - b.column)
    .map(cellText)
}

function sameRow(left: string[], right: string[]) {
  return (
    left.length > 0 &&
    left.length === right.length &&
    left.every((value, index) => value === right[index])
  )
}

function rowAnchor(table: DocumentTable, row: number) {
  const cell = table.cells.find((item) => item.row === row && item.column === 0)
  const value = cell?.text.trim() ?? ''
  return /^\d{1,3}$/.test(value) ? Number(value) : null
}

function firstAnchor(table: DocumentTable) {
  const rows = [...new Set(table.cells.map((cell) => cell.row))].sort(
    (a, b) => a - b,
  )
  return (
    rows.map((row) => rowAnchor(table, row)).find((value) => value !== null) ??
    null
  )
}

function lastAnchor(table: DocumentTable) {
  const rows = [...new Set(table.cells.map((cell) => cell.row))].sort(
    (a, b) => b - a,
  )
  for (const row of rows) {
    const value = rowAnchor(table, row)
    if (value !== null) return value
    const text = table.cells
      .filter((cell) => cell.row === row)
      .map((cell) => cell.text)
      .join(' ')
      .toLocaleLowerCase()
    if (/tổng|total|subtotal/.test(text)) return null
  }
  return null
}

function looksLikeLegacyContinuation(
  previous: DocumentTable,
  current: DocumentTable,
) {
  if (current.pageNo !== previous.pageNo + 1) return false
  if (previous.columns < 1 || current.columns < 1) return false
  const previousRow = previous.cells.find(
    (cell) => rowAnchor(previous, cell.row) !== null,
  )?.row
  const currentRow = current.cells.find(
    (cell) => rowAnchor(current, cell.row) !== null,
  )?.row
  const previousShape = new Set(
    previous.cells
      .filter((cell) => cell.row === previousRow)
      .map((cell) => cell.column),
  ).size
  const currentShape = new Set(
    current.cells
      .filter((cell) => cell.row === currentRow)
      .map((cell) => cell.column),
  ).size
  if (previousShape < 1 || previousShape !== currentShape) return false
  const previousEnd = lastAnchor(previous)
  const currentStart = firstAnchor(current)
  return previousEnd !== null && currentStart === previousEnd + 1
}

function fragmentRootId(
  table: DocumentTable,
  byId: Map<string, DocumentTable>,
) {
  const seen = new Set<string>()
  let current = table
  while (current.continuedFrom && !seen.has(current.id)) {
    seen.add(current.id)
    const parent = byId.get(current.continuedFrom)
    if (!parent) break
    current = parent
  }
  return current.id
}

/** Gộp fragment nối trang nhưng giữ pageNo riêng trên từng cell cho citation. */
export function mergeDocumentTables(
  input: DocumentTable[],
): MergedDocumentTable[] {
  const ordered = [...input].sort(
    (a, b) => a.pageNo - b.pageNo || a.id.localeCompare(b.id),
  )
  const byPage = new Map<number, DocumentTable[]>()
  for (const table of ordered) {
    const pageTables = byPage.get(table.pageNo) ?? []
    pageTables.push(table)
    byPage.set(table.pageNo, pageTables)
  }
  for (const [pageNo, currentPage] of byPage) {
    const previousPage = byPage.get(pageNo - 1)
    if (!previousPage) continue
    const previous = [...previousPage]
      .reverse()
      .find((table) => lastAnchor(table) !== null)
    const current = currentPage.find((table) => firstAnchor(table) !== null)
    if (
      previous &&
      current &&
      !current.continuedFrom &&
      looksLikeLegacyContinuation(previous, current)
    ) {
      current.continuedFrom = previous.id
      current.continued = true
    }
  }
  const byId = new Map(ordered.map((table) => [table.id, table]))
  const groups = new Map<string, DocumentTable[]>()

  for (const table of ordered) {
    const rootId = fragmentRootId(table, byId)
    const group = groups.get(rootId) ?? []
    group.push(table)
    groups.set(rootId, group)
  }

  return [...groups.values()].map((fragments) => {
    fragments.sort((a, b) => a.pageNo - b.pageNo || a.id.localeCompare(b.id))
    const first = fragments[0]
    const firstRow = Math.min(...first.cells.map((cell) => cell.row), 0)
    const header = rowSignature(first, firstRow)
    const cells: DocumentTableCell[] = []
    let rowOffset = 0

    fragments.forEach((fragment, fragmentIndex) => {
      const fragmentFirstRow = Math.min(
        ...fragment.cells.map((cell) => cell.row),
        0,
      )
      const fragmentHeader = rowSignature(fragment, fragmentFirstRow)
      const skipHeader = fragmentIndex > 0 && sameRow(header, fragmentHeader)
      const syntheticHeader =
        rowAnchor(fragment, fragmentFirstRow) !== null &&
        fragment.cells
          .filter((cell) => cell.row === fragmentFirstRow)
          .every((cell) => cell.header)
      const sourceRows = new Set(
        fragment.cells
          .filter((cell) => !skipHeader || cell.row !== fragmentFirstRow)
          .map((cell) => cell.row),
      )
      const rawRowCount = Math.max(
        0,
        ...[...sourceRows].map((row) => row - fragmentFirstRow + 1),
      )
      const rowCount = Math.max(0, rawRowCount - (skipHeader ? 1 : 0))

      for (const cell of fragment.cells) {
        if (skipHeader && cell.row === fragmentFirstRow) continue
        cells.push({
          ...cell,
          header:
            syntheticHeader && cell.row === fragmentFirstRow
              ? false
              : cell.header,
          row: rowOffset + cell.row - fragmentFirstRow - (skipHeader ? 1 : 0),
          pageNo: fragment.pageNo,
        })
      }
      rowOffset += rowCount
    })

    const pageNos = [
      ...new Set(fragments.map((fragment) => fragment.pageNo)),
    ].sort((a, b) => a - b)
    return {
      ...first,
      rows: Math.max(0, ...cells.map((cell) => cell.row + cell.rowSpan)),
      columns: Math.max(
        first.columns,
        ...cells.map((cell) => cell.column + cell.colSpan),
      ),
      continued:
        fragments.length > 1 ||
        fragments.some((fragment) => fragment.continued),
      continuedFrom: null,
      cells,
      pageStart: pageNos[0] ?? first.pageNo,
      pageEnd: pageNos.at(-1) ?? first.pageNo,
      pageNos,
      fragmentIds: fragments.map((fragment) => fragment.id),
    }
  })
}
