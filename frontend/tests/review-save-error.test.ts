import { describe, expect, it } from 'vitest'
import { ApiError, messageFromBody } from '../src/api/client'
import {
  EXPIRED_MESSAGE,
  READ_ONLY_MESSAGE,
  reviewErrorMessage,
  ROLE_DENIED_MESSAGE,
} from '../src/review/saveError'

const forbidden = (message: string) => new ApiError(403, message)

describe('reviewErrorMessage', () => {
  it('turns the English role error into a Vietnamese one', () => {
    expect(
      reviewErrorMessage(
        forbidden(
          "Insufficient role — required one of ['REVIEWER', 'ADMINISTRATOR'], got 'OPERATOR'",
        ),
        'x',
      ),
    ).toBe(ROLE_DENIED_MESSAGE)
  })

  it('says view-only and who to contact, even when the text mentions expiry', () => {
    expect(
      reviewErrorMessage(forbidden('Bạn chỉ có quyền xem hồ sơ này.'), 'x'),
    ).toBe(READ_ONLY_MESSAGE)
    expect(
      reviewErrorMessage(
        forbidden('Bạn chỉ có quyền xem hồ sơ này, hoặc quyền đã hết hạn.'),
        'x',
      ),
    ).toBe(READ_ONLY_MESSAGE)
  })

  it('reports an expired grant', () => {
    expect(
      reviewErrorMessage(forbidden('Quyền chia sẻ đã hết hạn.'), 'x'),
    ).toBe(EXPIRED_MESSAGE)
  })

  it('trusts the backend code over the wording', () => {
    const coded = (code: string, message: string) =>
      new ApiError(403, message, code)
    expect(
      reviewErrorMessage(
        coded(
          'ROLE_DENIED',
          'Chỉ người thẩm định hoặc quản trị viên được thẩm định.',
        ),
        'x',
      ),
    ).toBe(ROLE_DENIED_MESSAGE)
    expect(
      reviewErrorMessage(
        coded('ROLE_DENIED', 'Chỉ quản trị viên được duyệt hồ sơ.'),
        'x',
      ),
    ).toBe(ROLE_DENIED_MESSAGE)
    expect(
      reviewErrorMessage(
        coded('READ_ONLY', 'Bạn chỉ có quyền xem hồ sơ này.'),
        'x',
      ),
    ).toBe(READ_ONLY_MESSAGE)
    expect(
      reviewErrorMessage(
        coded(
          'ACL_DENIED',
          'Bạn không có quyền trên hồ sơ này, hoặc quyền đã hết hạn.',
        ),
        'x',
      ),
    ).toBe(EXPIRED_MESSAGE)
  })

  it('reads code and message from an object detail', () => {
    expect(
      messageFromBody(403, {
        detail: {
          code: 'ROLE_DENIED',
          message: 'Chỉ quản trị viên được duyệt hồ sơ.',
        },
      }),
    ).toEqual({
      code: 'ROLE_DENIED',
      message: 'Chỉ quản trị viên được duyệt hồ sơ.',
    })
    expect(
      messageFromBody(403, { detail: 'Bạn chỉ có quyền xem hồ sơ này.' }),
    ).toEqual({
      code: undefined,
      message: 'Bạn chỉ có quyền xem hồ sơ này.',
    })
  })

  it('keeps other errors and falls back for unknown ones', () => {
    expect(reviewErrorMessage(new Error('boom'), 'x')).toBe('boom')
    expect(reviewErrorMessage('lạ', 'Không lưu được')).toBe('Không lưu được')
  })
})
