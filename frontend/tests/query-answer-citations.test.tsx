import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { AnswerView } from '../src/components/QueryHistoryPanel'
import { answerBlocks, citesByBlock } from '../src/components/queryAnswer'

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
