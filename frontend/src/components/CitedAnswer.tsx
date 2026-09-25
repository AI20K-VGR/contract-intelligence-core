import { useMemo, type ReactNode } from 'react'
import type { ClauseNode, DossierSearchHit } from '../api/structure'
import { searchCites, type SearchCite } from '../structure/citations'
import { branchMap, toneAt } from '../structure/display'
import { CiteBadge } from './StructureViewShell'

/** Vị trí hết dòng chứa đoạn khớp. Số đứng sau cả câu trích, không đứng sau nhãn đầu dòng. */
function locateEnd(answer: string, needle: string): number {
  const flat: string[] = []
  const ends: number[] = []
  let pendingSpace = false
  for (let index = 0; index < answer.length; index += 1) {
    if (/\s/.test(answer[index] ?? '')) {
      pendingSpace = flat.length > 0
      continue
    }
    if (pendingSpace) {
      flat.push(' ')
      ends.push(index)
      pendingSpace = false
    }
    flat.push((answer[index] ?? '').toLowerCase())
    ends.push(index + 1)
  }
  const at = flat.join('').indexOf(needle)
  const matchEnd = at < 0 ? answer.length : (ends[at + needle.length - 1] ?? answer.length)
  const lineEnd = answer.indexOf('\n', matchEnd)
  return lineEnd < 0 ? answer.length : lineEnd
}

/** OCR trả về từng dòng; câu trả lời hiện thành một đoạn, không giữ ngắt dòng đó. */
function flow(text: string) {
  return text.replace(/[ \t]*\n+[ \t]*/g, ' ').replace(/[ \t]{2,}/g, ' ')
}

function placeCites(answer: string, cites: SearchCite[]) {
  const marks = cites
    .map((cite) => ({ cite, at: locateEnd(answer, cite.quote) }))
    .sort((left, right) => left.at - right.at || left.cite.n - right.cite.n)
  return marks
}

export function CitedAnswer({
  answer,
  hits,
  nodes,
  citationOf,
  activeId,
  onCite,
}: {
  answer: string
  hits: DossierSearchHit[]
  nodes: ClauseNode[]
  citationOf: ReadonlyMap<string, number>
  activeId: string | null
  onCite: (id: string) => void
}) {
  const cites = useMemo(
    () => searchCites(nodes, hits, citationOf, answer),
    [nodes, hits, citationOf, answer],
  )
  const branches = useMemo(() => branchMap(nodes), [nodes])
  const marks = useMemo(() => placeCites(answer, cites), [answer, cites])
  const pieces: ReactNode[] = []
  let cursor = 0
  marks.forEach((mark, index) => {
    const at = Math.max(cursor, Math.min(mark.at, answer.length))
    if (at > cursor) pieces.push(flow(answer.slice(cursor, at)))
    pieces.push(
      <span key={mark.cite.id} className="mx-0.5 inline-block align-super">
        <CiteBadge
          active={activeId === mark.cite.id}
          n={mark.cite.n}
          tone={toneAt(branches.get(mark.cite.id) ?? index)}
          onClick={() => onCite(mark.cite.id)}
        />
      </span>,
    )
    cursor = at
  })
  if (cursor < answer.length) pieces.push(flow(answer.slice(cursor)))

  return (
    <div className="font-body-sm text-body-sm leading-relaxed text-on-surface">
      {pieces}
    </div>
  )
}
