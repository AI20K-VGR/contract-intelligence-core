import { describe, expect, it } from 'vitest'

import { ocrErrorDetail, ocrErrorMessage } from '../src/api/dossiers'

const NOT_READY =
  'Hệ thống chưa sẵn sàng để đọc tài liệu. Vui lòng báo quản trị viên.'

describe('ocrErrorMessage', () => {
  it('hides configuration problems behind one admin message', () => {
    expect(
      ocrErrorMessage(
        'SKIPPED: OpenAI vision unavailable: RuntimeError: OPENAI_API_KEY is not set',
      ),
    ).toBe(NOT_READY)
    expect(
      ocrErrorMessage('Mistral OCR engine disabled in configuration'),
    ).toBe(NOT_READY)
    expect(ocrErrorMessage('AuthenticationError: invalid key')).toBe(NOT_READY)
  })

  it('prefers the specific cause over the wrapping "unavailable"', () => {
    expect(
      ocrErrorMessage(
        'SKIPPED: OpenAI vision unavailable: APIConnectionError: Connection error.',
      ),
    ).toBe('Mất kết nối khi đọc tài liệu. Vui lòng bấm "Đọc lại".')
    expect(
      ocrErrorMessage('Gemini vision unavailable: ValueError: odd reply'),
    ).toBe('Dịch vụ đọc tài liệu đang gặp sự cố. Vui lòng thử lại sau.')
  })

  it('explains file problems', () => {
    expect(ocrErrorMessage('source document is not a valid PDF')).toBe(
      'Tệp không phải PDF hợp lệ. Vui lòng kiểm tra và tải lại tệp.',
    )
  })

  it('falls back to a generic sentence for unknown errors', () => {
    expect(ocrErrorMessage('KeyError: bbox')).toBe(
      'Không đọc được tài liệu. Vui lòng bấm "Đọc lại"; nếu vẫn lỗi, báo quản trị viên.',
    )
  })
})

describe('ocrErrorDetail', () => {
  it('keeps the original text without the SKIPPED prefix', () => {
    expect(
      ocrErrorDetail('SKIPPED: APIConnectionError: Connection error.'),
    ).toBe('APIConnectionError: Connection error.')
  })
})

describe('ocrErrorMessage with numbers (PR #122 review)', () => {
  it('reads a bare number as a page or size, not an HTTP code', () => {
    expect(ocrErrorMessage('page 401: ReadTimeout')).toBe(
      'Đọc tài liệu quá lâu. Vui lòng bấm "Đọc lại".',
    )
    expect(ocrErrorMessage('chunk 500 timed out')).toBe(
      'Đọc tài liệu quá lâu. Vui lòng bấm "Đọc lại".',
    )
  })

  it('still reads an HTTP code that comes with its context', () => {
    expect(ocrErrorMessage('Upstream returned HTTP 401')).toBe(NOT_READY)
    expect(ocrErrorMessage('Mistral failed: status_code=503')).toBe(
      ocrErrorMessage('ServiceUnavailable'),
    )
    expect(ocrErrorMessage('ServiceUnavailable')).not.toBe(NOT_READY)
  })
})
