import { buildFreeformTree } from './freeform'
import { buildNumberedTree } from './numbered'
import type { ClauseNode, OcrLine, StructureMode } from './types'

export {
  STRUCTURE_MODE_KEY,
  STRUCTURE_VIEW_KEY,
  parseStructureMode,
  parseStructureView,
  structureModeLabel,
  structureModes,
  structureViews,
} from './types'
export type { OcrLine, StructureMode, StructureView } from './types'
export { parseMarker } from './markers'
export { buildNumberedTree } from './numbered'
export { buildFreeformTree } from './freeform'

/** Dựng cây cấu trúc từ dòng OCR thô theo loại tài liệu người dùng chọn. */
export function buildStructureTree(
  lines: OcrLine[],
  mode: StructureMode,
): ClauseNode[] {
  if (mode === 'tables') return []
  return mode === 'freeform'
    ? buildFreeformTree(lines)
    : buildNumberedTree(lines)
}

/** Infer a safe first view when upload metadata did not specify a mode. */
export function inferStructureMode(
  lines: OcrLine[],
  hasTables: boolean,
): StructureMode {
  if (buildNumberedTree(lines).length > 0) return 'numbered'
  if (hasTables) return 'tables'
  if (buildFreeformTree(lines).length > 0) return 'freeform'
  return 'numbered'
}
