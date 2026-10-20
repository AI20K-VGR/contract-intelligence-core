export type ConflictRisk = 'high' | 'resolved'
export type ConflictChoice =
  'source1' | 'source2' | 'rejected' | 'skipped' | 'overlay'

export type ConflictSource = {
  id: 'source1' | 'source2'
  label: string
  value: string
  unit: string
  context: string
  location: string
  quoteBefore: string
  highlight: string
  quoteAfter: string
  field: string
}

export type ClauseConflict = {
  id: string
  code: string
  title: string
  field: string
  comparison: string
  location: string
  risk: ConflictRisk
  badge: string
  diagnosis: string
  source1: ConflictSource
  source2: ConflictSource
  choice?: ConflictChoice
}

export const conflictDossier = {
  title: 'Hợp đồng Cung ứng Dịch vụ Viễn thông & CNTT',
  code: 'LX-2024-EPC-089',
}

export const clauseConflicts: ClauseConflict[] = [
  {
    id: 'CF-01',
    code: '#01',
    title: 'Mức phạt vi phạm nghĩa vụ',
    field: 'penalty_general',
    comparison: 'penalty_general: 0.12% vs 0.1%',
    location: 'Thân hợp đồng · Trang 14-15',
    risk: 'high',
    badge: 'Rủi ro cao',
    diagnosis:
      'Nguồn 1: 0,12% ↔ Nguồn 2: 0,1%. Hai nguồn khác biệt giá trị — chưa xác định ưu tiên.',
    source1: {
      id: 'source1',
      label: 'Nguồn 1',
      value: '0,12%',
      unit: 'percent',
      context: 'thân HĐ · penalty_general',
      location: 'Khoản 7.1 · Trang 14:',
      quoteBefore: 'Mức phạt vi phạm nghĩa vụ thanh toán là ',
      highlight: '0,12%/ngày',
      quoteAfter: ' tính trên số tiền chậm trả.',
      field: 'field_amt_1',
    },
    source2: {
      id: 'source2',
      label: 'Nguồn 2',
      value: '0,1%',
      unit: 'percent',
      context: 'thân HĐ · Điều 7. Phạt và giới hạn trách nhiệm',
      location: 'Khoản 7.3 · Trang 15:',
      quoteBefore: 'Tổng mức phạt do vi phạm hoặc bồi thường không vượt quá ',
      highlight: '0,1%/ngày',
      quoteAfter: ' đối với mọi hành vi.',
      field: 'field_amt_18',
    },
  },
  {
    id: 'CF-02',
    code: '#02',
    title: 'Thời hạn thông báo chấm dứt',
    field: 'notice_period',
    comparison: 'notice_period: 30 ngày vs 45 ngày',
    location: 'Điều 12.2 vs Phụ lục A',
    risk: 'resolved',
    badge: 'Đã giải quyết',
    choice: 'source1',
    diagnosis:
      'Nguồn 1: 30 ngày ↔ Nguồn 2: 45 ngày. Ưu tiên thời hạn ngắn hơn tại thân hợp đồng.',
    source1: {
      id: 'source1',
      label: 'Nguồn 1',
      value: '30',
      unit: 'ngày',
      context: 'thân HĐ · notice_period',
      location: 'Điều 12.2 · Trang 22:',
      quoteBefore: 'Bên muốn chấm dứt hợp đồng phải thông báo trước ít nhất ',
      highlight: '30 ngày',
      quoteAfter: ' làm việc.',
      field: 'field_term_12',
    },
    source2: {
      id: 'source2',
      label: 'Nguồn 2',
      value: '45',
      unit: 'ngày',
      context: 'Phụ lục A · Điều kiện chấm dứt',
      location: 'Phụ lục A · Mục 4:',
      quoteBefore: 'Thời hạn thông báo chấm dứt dịch vụ là ',
      highlight: '45 ngày',
      quoteAfter: ' kể từ ngày bên kia nhận được văn bản.',
      field: 'field_term_a4',
    },
  },
  {
    id: 'CF-03',
    code: '#03',
    title: 'Thẩm quyền giải quyết tranh chấp',
    field: 'jurisdiction',
    comparison: 'jurisdiction: VIAC vs Tòa án TP. Hà Nội',
    location: 'Điều 18.1 vs Điều 18.4',
    risk: 'high',
    badge: 'Rủi ro cao',
    diagnosis:
      'Nguồn 1: VIAC ↔ Nguồn 2: TAND TP. Hà Nội. Xung đột cơ quan tài phán — cần chốt một diễn đàn duy nhất.',
    source1: {
      id: 'source1',
      label: 'Nguồn 1',
      value: 'VIAC',
      unit: 'trọng tài',
      context: 'thân HĐ · jurisdiction',
      location: 'Điều 18.1 · Trang 31:',
      quoteBefore: 'Mọi tranh chấp được giải quyết tại ',
      highlight: 'VIAC',
      quoteAfter: ' theo quy tắc tố tụng trọng tài hiện hành.',
      field: 'field_jur_1',
    },
    source2: {
      id: 'source2',
      label: 'Nguồn 2',
      value: 'TAND HN',
      unit: 'tòa án',
      context: 'thân HĐ · Điều 18.4',
      location: 'Điều 18.4 · Trang 32:',
      quoteBefore: 'Thẩm quyền giải quyết thuộc ',
      highlight: 'Tòa án nhân dân TP. Hà Nội',
      quoteAfter: '.',
      field: 'field_jur_4',
    },
  },
  {
    id: 'CF-04',
    code: '#04',
    title: 'Mức trần bồi thường thiệt hại',
    field: 'liability_cap',
    comparison: 'liability_cap: 100% vs 50% tổng giá trị',
    location: 'Điều 9.4 · Trang 19',
    risk: 'resolved',
    badge: 'Đã giải quyết',
    choice: 'source2',
    diagnosis:
      'Nguồn 1: 100% ↔ Nguồn 2: 50%. Đã chọn mức trần 50% theo nguồn 2.',
    source1: {
      id: 'source1',
      label: 'Nguồn 1',
      value: '100%',
      unit: 'tổng giá trị',
      context: 'thân HĐ · liability_cap',
      location: 'Khoản 9.4 · Trang 19:',
      quoteBefore: 'Trần bồi thường thiệt hại không vượt quá ',
      highlight: '100% tổng giá trị dịch vụ',
      quoteAfter: ' đã thanh toán.',
      field: 'field_cap_9',
    },
    source2: {
      id: 'source2',
      label: 'Nguồn 2',
      value: '50%',
      unit: 'tổng giá trị',
      context: 'Phụ lục tài chính · mức trần',
      location: 'Phụ lục TC · Mục 3.b:',
      quoteBefore: 'Tổng trách nhiệm bồi thường tối đa bằng ',
      highlight: '50% tổng giá trị hợp đồng',
      quoteAfter: '.',
      field: 'field_cap_tc',
    },
  },
]
