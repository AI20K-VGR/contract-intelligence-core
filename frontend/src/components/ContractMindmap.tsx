import type { ClauseNode } from '../api/structure'
import { StructureMindmap } from './StructureMindmap'

/** Backward-compatible name for a mindmap backed by the active dossier. */
export function ContractMindmap({
  title = 'Cấu trúc hợp đồng',
  subtitle,
  nodes = [],
}: {
  title?: string
  subtitle?: string | null
  nodes?: ClauseNode[]
}) {
  return <StructureMindmap title={title} subtitle={subtitle} nodes={nodes} />
}
