import type { ClauseNode } from '../api/structure'
import { StructureMindmap } from './StructureMindmap'

/** Backward-compatible name for a mindmap backed by the active dossier. */
export function ContractMindmap({
  title = 'Cấu trúc hợp đồng',
  nodes = [],
}: {
  title?: string
  nodes?: ClauseNode[]
}) {
  return <StructureMindmap title={title} nodes={nodes} />
}
