import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { AnswerView } from '../src/components/QueryHistoryPanel'
import {
  ANSWER_STATE_LABELS,
  answerBlocks,
  citesByBlock,
} from '../src/components/queryAnswer'

const ANSWER = [
  'Điều 4. Thanh toán',
  '4.1. Bên A thanh toán trong 30 ngày kể từ ngày nhận hoá đơn.',
  '4.2. Chậm thanh toán chịu lãi 0,05% mỗi ngày.',
].join('\n')

const MATCHED = { quote: '4.1. Bên A thanh toán trong 30 ngày', pageNo: 3 }
const UNMATCHED = { quote: 'Bất khả kháng gồm thiên tai, hoả hoạn', pageNo: 9 }
const EMPTY = { quote: '', pageNo: 5 }

describe('citesByBlock', () => {
  it('puts a matching citation on its own block', () => {
    const blocks = answerBlocks(ANSWER)
    const { placed, unplaced } = citesByBlock(blocks, [MATCHED])
    expect(placed.get(1)).toEqual([{ citation: MATCHED, n: 1 }])
    expect(unplaced).toEqual([])
  })

  it('keeps an unmatched citation apart instead of on the last block', () => {
    const blocks = answerBlocks(ANSWER)
    const { placed, unplaced } = citesByBlock(blocks, [MATCHED, UNMATCHED])
    expect(placed.get(blocks.length - 1)).toBeUndefined()
    expect(unplaced).toEqual([{ citation: UNMATCHED, n: 2 }])
  })

  it('keeps a citation with an empty quote, with its original number', () => {
    const blocks = answerBlocks(ANSWER)
    const { placed, unplaced } = citesByBlock(blocks, [
      EMPTY,
      MATCHED,
      UNMATCHED,
    ])
    expect(unplaced).toEqual([
      { citation: EMPTY, n: 1 },
      { citation: UNMATCHED, n: 3 },
    ])
    expect(placed.get(1)).toEqual([{ citation: MATCHED, n: 2 }])
  })

  it('gives one number to the lines of the same clause in the same document', () => {
    const answer = [
      'Điều 1. Định nghĩa',
      '1.3. Trường hợp một thuật ngữ có nhiều cách hiểu, ưu tiên cách hiểu đã được hai bên phê duyệt.',
      '1.4. Ngày làm việc không gồm thứ Bảy.',
    ].join('\n')
    const firstLine = {
      quote: '1.3. Trường hợp một thuật ngữ có nhiều cách hiểu',
      pageNo: 2,
      documentId: 'doc_contract',
    }
    const secondLine = {
      quote: 'ưu tiên cách hiểu đã được hai bên phê duyệt',
      pageNo: 2,
      documentId: 'doc_contract',
    }
    const next = {
      quote: '1.4. Ngày làm việc không gồm thứ Bảy',
      pageNo: 2,
      documentId: 'doc_contract',
    }
    const blocks = answerBlocks(answer)
    const { placed } = citesByBlock(blocks, [firstLine, secondLine, next])
    expect(placed.get(1)).toEqual([{ citation: firstLine, n: 1 }])
    // Số đánh liên tục sau khi gộp: khoản 1.4 là số 2, không phải 3.
    expect(placed.get(2)).toEqual([{ citation: next, n: 2 }])
  })

  it('keeps two places of the same document on different pages apart', () => {
    // Một mục trích hai điều khác trang: bấm mỗi số mở một chỗ khác nhau.
    const answer = [
      'Điều 3. Thanh toán và phạt chậm trả',
      '3.1. Bên A thanh toán trong 30 ngày và chịu phạt chậm trả 0,05% mỗi ngày.',
    ].join('\n')
    const payment = {
      quote: 'Bên A thanh toán trong 30 ngày',
      pageNo: 2,
      documentId: 'doc_contract',
    }
    const penalty = {
      quote: 'chịu phạt chậm trả 0,05% mỗi ngày',
      pageNo: 7,
      documentId: 'doc_contract',
    }
    const blocks = answerBlocks(answer)
    const { placed } = citesByBlock(blocks, [payment, penalty])
    expect(placed.get(1)).toEqual([
      { citation: payment, n: 1 },
      { citation: penalty, n: 2 },
    ])
  })

  it('keeps a number for each clause quoted on the same page (PR #122 review)', () => {
    // Câu trả lời tổng hợp trích liền 5.1, 5.2, 5.3 cùng trang 1: mỗi khoản
    // mở một chỗ khác nhau nên giữ ba số; dòng nối của 5.2 không thêm số.
    const answer = [
      'Điều 5. Nghĩa vụ các bên',
      '5. Các nghĩa vụ chính: 5.1. Bên A giao hàng đúng hạn; 5.2. Bên B thanh toán đủ trong 30 ngày kể từ ngày nhận hoá đơn; 5.3. Hai bên bảo mật thông tin.',
    ].join('\n')
    const doc = { pageNo: 1, documentId: 'doc_contract' }
    const first = { ...doc, quote: '5.1. Bên A giao hàng đúng hạn' }
    const second = { ...doc, quote: '5.2. Bên B thanh toán đủ trong 30 ngày' }
    const secondLine = { ...doc, quote: 'kể từ ngày nhận hoá đơn' }
    const third = { ...doc, quote: '5.3. Hai bên bảo mật thông tin' }
    const blocks = answerBlocks(answer)
    const { placed } = citesByBlock(blocks, [first, second, secondLine, third])
    expect(placed.get(1)).toEqual([
      { citation: first, n: 1 },
      { citation: second, n: 2 },
      { citation: third, n: 3 },
    ])
  })

  it('keeps a number for each point a), b), c) of the same clause', () => {
    // Các điểm a), b), c) là ba nút riêng trên cây: mỗi điểm một số.
    const answer = [
      'Điều 7. Nghĩa vụ của Bên B',
      '7.1. Bên B có nghĩa vụ: a) giao hàng đúng hạn; b) bảo hành 12 tháng; c) bảo mật thông tin.',
    ].join('\n')
    const doc = { pageNo: 4, documentId: 'doc_contract' }
    const lead = { ...doc, quote: '7.1. Bên B có nghĩa vụ:' }
    const a = { ...doc, quote: 'a) giao hàng đúng hạn' }
    const b = { ...doc, quote: 'b) bảo hành 12 tháng' }
    const c = { ...doc, quote: 'c) bảo mật thông tin' }
    const blocks = answerBlocks(answer)
    const { placed } = citesByBlock(blocks, [lead, a, b, c])
    expect(placed.get(1)?.map((entry) => entry.n)).toEqual([1, 2, 3, 4])
  })

  it('merges a wrapped line that starts with an amount or a date (PR #122 review)', () => {
    // "1.000.000.000 đồng" và "17.10.2026" không phải số khoản: dòng nối.
    const answer = [
      'Điều 6. Giá trị hợp đồng',
      '6.1. Tổng giá trị là 1.000.000.000 đồng, thanh toán trước ngày 17.10.2026 hai bên ký biên bản.',
    ].join('\n')
    const doc = { pageNo: 3, documentId: 'doc_contract' }
    const first = { ...doc, quote: '6.1. Tổng giá trị là' }
    const amount = {
      ...doc,
      quote: '1.000.000.000 đồng, thanh toán trước ngày',
    }
    const date = { ...doc, quote: '17.10.2026 hai bên ký biên bản' }
    const blocks = answerBlocks(answer)
    const { placed } = citesByBlock(blocks, [first, amount, date])
    expect(placed.get(1)).toEqual([{ citation: first, n: 1 }])
  })

  it('merges a wrapped line that starts with a number into its clause', () => {
    // "30 ngày …" là dòng 2 của khoản 5.2, không phải khoản mới: cùng một số.
    const answer = [
      'Điều 5. Thanh toán',
      '5.2. Bên B thanh toán đủ trong vòng 30 ngày kể từ ngày nhận hoá đơn.',
    ].join('\n')
    const doc = { pageNo: 2, documentId: 'doc_contract' }
    const first = { ...doc, quote: '5.2. Bên B thanh toán đủ trong vòng' }
    const wrapped = { ...doc, quote: '30 ngày kể từ ngày nhận hoá đơn' }
    const blocks = answerBlocks(answer)
    const { placed } = citesByBlock(blocks, [first, wrapped])
    expect(placed.get(1)).toEqual([{ citation: first, n: 1 }])
  })

  it('keeps old citations without a document apart unless the quote repeats', () => {
    const blocks = answerBlocks(ANSWER)
    const other = {
      quote: 'thanh toán trong 30 ngày kể từ ngày nhận',
      pageNo: 3,
    }
    const { placed } = citesByBlock(blocks, [MATCHED, other, MATCHED])
    expect(placed.get(1)).toEqual([
      { citation: MATCHED, n: 1 },
      { citation: other, n: 2 },
    ])
  })

  it('keeps the contract and the annex apart even on the same clause', () => {
    const blocks = answerBlocks(ANSWER)
    const contract = { ...MATCHED, documentId: 'doc_contract' }
    const annex = { ...MATCHED, documentId: 'doc_annex' }
    const { placed } = citesByBlock(blocks, [contract, annex])
    expect(placed.get(1)).toEqual([
      { citation: contract, n: 1 },
      { citation: annex, n: 2 },
    ])
  })
})

describe('AnswerView', () => {
  it('lists unplaced citations under "Trích dẫn khác", not on the last block', () => {
    const html = renderToStaticMarkup(
      <AnswerView answer={ANSWER} citations={[MATCHED, UNMATCHED, EMPTY]} />,
    )
    const [body, others] = html.split(
      'Trích dẫn khác (chưa xác định đoạn liên quan):',
    )
    expect(others).toBeDefined()
    // Số 1 nằm ở khoản 4.1; số 2 và 3 chỉ có trong nhóm "Trích dẫn khác".
    expect(body).toContain('title="Trích dẫn 1 · trang 3"')
    expect(body).not.toContain('title="Trích dẫn 2')
    expect(body).not.toContain('title="Trích dẫn 3')
    expect(others).toContain('title="Trích dẫn 2 · trang 9"')
    expect(others).toContain('title="Trích dẫn 3 · trang 5"')
  })

  it('shows no "Trích dẫn khác" group when every citation is placed', () => {
    const html = renderToStaticMarkup(
      <AnswerView answer={ANSWER} citations={[MATCHED]} />,
    )
    expect(html).not.toContain('Trích dẫn khác')
  })
})

describe('ANSWER_STATE_LABELS', () => {
  it('words each unusual state by how much evidence the answer has', () => {
    expect(ANSWER_STATE_LABELS.NEEDS_REVIEW?.label).toBe(
      'Chưa đủ căn cứ, cần kiểm lại',
    )
    expect(ANSWER_STATE_LABELS.INSUFFICIENT_EVIDENCE?.label).toBe(
      'Thiếu căn cứ trong hồ sơ',
    )
    expect(ANSWER_STATE_LABELS.BLOCKED?.label).toBe('Không được trả lời')
    // Câu trả lời có căn cứ là trường hợp bình thường: không gắn nhãn.
    expect(ANSWER_STATE_LABELS.ANSWERED).toBeUndefined()
  })
})
