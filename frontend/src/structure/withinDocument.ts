/*
 * Xung đột có thể nằm giữa hai tài liệu (hợp đồng và phụ lục) hoặc ngay trong
 * một hợp đồng. Trường hợp sau, cả hai vế trích dẫn cùng một tài liệu, nên
 * màn đối soát phải hiện hai vị trí trên cùng file thay vì tìm "phụ lục".
 */
export function withinDocumentId(spot: {
  sides: { documentId: string }[]
}): string | null {
  const ids = spot.sides.map((side) => side.documentId).filter(Boolean)
  if (ids.length < 2) return null
  return ids.every((id) => id === ids[0]) ? ids[0] : null
}

export function withinSideLabel(index: number) {
  return `Vế ${index + 1}`
}
