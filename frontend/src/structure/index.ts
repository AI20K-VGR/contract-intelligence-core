import { buildFreeformTree } from './freeform'
import { buildNumberedTree } from './numbered'
import type { ClauseNode, OcrLine, StructureMode } from './types'

export {
  STRUCTURE_MODE_KEY,
  parseStructureMode,
  structureModeLabel,
  structureModes,
} from './types'
export type { OcrLine, StructureMode } from './types'
export { parseMarker } from './markers'
export { buildNumberedTree } from './numbered'
export { buildFreeformTree } from './freeform'

/** Dựng cây cấu trúc từ dòng OCR thô theo loại tài liệu người dùng chọn. */
export function buildStructureTree(
  lines: OcrLine[],
  mode: StructureMode,
): ClauseNode[] {
  return mode === 'freeform'
    ? buildFreeformTree(lines)
    : buildNumberedTree(lines)
}
