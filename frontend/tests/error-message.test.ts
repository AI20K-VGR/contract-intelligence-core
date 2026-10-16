import { describe, expect, it, vi } from 'vitest'
import {
  LOGIN_NETWORK_MESSAGE,
  NETWORK_MESSAGE,
  userErrorMessage,
} from '../src/api/errorMessage'

describe('userErrorMessage', () => {
  it.each([
    'Failed to fetch',
    'NetworkError when attempting to fetch resource.',
    'Load failed',
  ])('turns the browser network error "%s" into Vietnamese', (message) => {
    expect(userErrorMessage(new TypeError(message), 'fallback')).toBe(
      NETWORK_MESSAGE,
    )
  })

  it('uses the login wording when given', () => {
    expect(
      userErrorMessage(
        new TypeError('Failed to fetch'),
        'fallback',
        LOGIN_NETWORK_MESSAGE,
      ),
    ).toBe(LOGIN_NETWORK_MESSAGE)
  })

  it('keeps messages already written in Vietnamese', () => {
    expect(
      userErrorMessage(new Error('Email doanh nghiệp không hợp lệ.'), 'x'),
    ).toBe('Email doanh nghiệp không hợp lệ.')
  })

  it('hides English or technical messages behind the fallback', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    expect(
      userErrorMessage(
        new Error('Invalid semantic payload'),
        'Không đọc được kết quả.',
      ),
    ).toBe('Không đọc được kết quả.')
    expect(warn).toHaveBeenCalledWith(
      '[Lỗi kỹ thuật]',
      'Invalid semantic payload',
    )
    expect(userErrorMessage('oops', 'Thử lại.')).toBe('Thử lại.')
    warn.mockRestore()
  })
})
