import { describe, expect, it } from 'vitest'
import { ApiError } from '../src/api/client'
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

  it('keeps other errors and falls back for unknown ones', () => {
    expect(reviewErrorMessage(new Error('boom'), 'x')).toBe('boom')
    expect(reviewErrorMessage('lạ', 'Không lưu được')).toBe('Không lưu được')
  })
})
