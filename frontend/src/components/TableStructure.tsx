import { useEffect, useState } from 'react'
import {
  listDocumentTables,
  structureErrorMessage,
  type ClauseNode,
  type DocumentTable,
  type DocumentTableCell,
} from '../api/structure'
import {
  mergeDocumentTables,
  type MergedDocumentTable,
} from '../structure/tables'
import { MaterialIcon } from './icons'

function cellAt(table: DocumentTable, row: number, column: number) {
  return table.cells.find((cell) => cell.row === row && cell.column === column)
}

function covered(table: DocumentTable, row: number, column: number) {
  return table.cells.some(
    (cell) =>
      row >= cell.row &&
      row < cell.row + cell.rowSpan &&
      column >= cell.column &&
      column < cell.column + cell.colSpan &&
      !(cell.row === row && cell.column === column),
  )
}

function tableNode(table: MergedDocumentTable, citeNo: number): ClauseNode {
  const pageNo = table.pageStart || table.pageNo || 1
  const cellBoxes = table.cells.flatMap((cell) =>
    cell.bbox ? [{ pageNo: cell.pageNo || pageNo, bbox: cell.bbox }] : [],
  )
  const regions = table.bbox
    ? [{ pageNo, bbox: table.bbox }, ...cellBoxes]
    : cellBoxes
  return {
    id: table.id,
    nodeType: 'table',
    label: `Bảng ${citeNo}`,
    number: String(citeNo),
    title: `Bảng ${citeNo}`,
    text: table.cells
      .map((cell) => cell.text)
      .filter(Boolean)
      .join(' '),
    pageStart: table.pageNo || 1,
    pageEnd: table.pageEnd || pageNo,
    confidence: null,
    regions,
    children: [],
  }
}

function TableGrid({ table }: { table: MergedDocumentTable }) {
  const rowCount = Math.max(
    table.rows,
    ...table.cells.map((cell) => cell.row + cell.rowSpan),
    0,
  )
  const columnCount = Math.max(
    table.columns,
    ...table.cells.map((cell) => cell.column + cell.colSpan),
    0,
  )
  const rows = Array.from({ length: rowCount }, (_, row) => row)

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left font-body-sm text-body-sm text-on-surface">
        <tbody>
          {rows.map((row) => (
            <tr key={row}>
              {Array.from({ length: columnCount }, (_, column) => {
                if (covered(table, row, column)) return null
                const cell = cellAt(table, row, column)
                return <Cell key={`${row}-${column}`} cell={cell} />
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Cell({ cell }: { cell: DocumentTableCell | undefined }) {
  const header = cell?.header === true
  const Tag = header ? 'th' : 'td'
  return (
    <Tag
      className={`border border-outline-variant/40 px-3 py-2 align-top ${
        header
          ? 'bg-surface-container font-semibold text-on-surface'
          : 'bg-surface-container-lowest'
      }`}
      colSpan={cell && cell.colSpan > 1 ? cell.colSpan : undefined}
      rowSpan={cell && cell.rowSpan > 1 ? cell.rowSpan : undefined}
    >
      {cell?.text || '—'}
    </Tag>
  )
}

export function TableStructure({
  documentId,
  query,
  activeId,
  onCite,
}: {
  documentId: string
  query: string
  activeId?: string | null
  onCite?: (node: ClauseNode, citeNo: number) => void
}) {
  const [tables, setTables] = useState<DocumentTable[] | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    setTables(null)
    setError(null)
    listDocumentTables(documentId, controller.signal)
      .then((next) => {
        if (!controller.signal.aborted) setTables(next)
      })
      .catch((cause: unknown) => {
        const message = structureErrorMessage(cause)
        if (message && !controller.signal.aborted) setError(message)
      })
    return () => controller.abort()
  }, [documentId])

  const needle = query.trim().toLowerCase()
  const visible = mergeDocumentTables(tables ?? [])
    .map((table, index) => ({ table, index }))
    .filter(({ table }) => table.cells.length > 0)
    .filter(({ table }) => {
      if (!needle) return true
      return table.cells.some((cell) =>
        cell.text.toLowerCase().includes(needle),
      )
    })

  if (error) {
    return (
      <p className="rounded-xl bg-error-container px-6 py-4 font-body-sm text-body-sm text-on-error-container">
        {error}
      </p>
    )
  }
  if (!tables) {
    return (
      <p className="font-body-sm text-body-sm text-on-surface-variant">
        Đang tải các bảng OCR…
      </p>
    )
  }
  if (visible.length === 0) {
    return (
      <div className="flex h-48 items-center rounded-xl bg-surface-container-lowest px-6 shadow-sm">
        <p className="font-body-sm text-body-sm text-on-surface-variant">
          {needle
            ? `Không có bảng khớp “${query.trim()}”.`
            : 'OCR chưa trích được bảng nào trong hồ sơ này.'}
        </p>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-space-md pb-16">
      {visible.map(({ table, index }) => (
        <section
          key={table.id}
          className="overflow-hidden rounded-xl bg-surface-container-lowest shadow-sm"
        >
          <div className="flex items-center gap-space-sm border-b border-outline-variant/20 px-space-md py-3">
            <MaterialIcon
              name="table_chart"
              className="text-[18px] text-secondary"
            />
            <h2 className="font-title-sm text-title-sm text-on-surface">
              Bảng {index + 1}
            </h2>
            {onCite ? (
              <button
                className={`inline-flex h-5 min-w-5 items-center justify-center rounded-full border px-1 text-[11px] font-semibold leading-none ${
                  activeId === table.id
                    ? 'border-[#0b1f3a] bg-[#0b1f3a] text-white'
                    : 'border-slate-300 bg-white text-slate-700 hover:border-slate-500'
                }`}
                type="button"
                onClick={() => onCite(tableNode(table, index + 1), index + 1)}
              >
                {index + 1}
              </button>
            ) : null}
            <span className="font-body-sm text-body-sm text-on-surface-variant">
              Trang {table.pageStart || '—'}
              {table.pageEnd > table.pageStart ? `–${table.pageEnd}` : ''}
              {table.continued ? ' · nối trang' : ''}
              {table.rows > 0
                ? ` · ${table.rows} dòng × ${table.columns} cột`
                : ''}
            </span>
          </div>
          <TableGrid table={table} />
        </section>
      ))}
    </div>
  )
}
