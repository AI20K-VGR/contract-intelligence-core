import { beforeEach, describe, expect, it, vi } from 'vitest'

const { requestJson } = vi.hoisted(() => ({ requestJson: vi.fn() }))

vi.mock('../src/api/client', async () => {
  const actual =
    await vi.importActual<typeof import('../src/api/client')>(
      '../src/api/client',
    )
  return { ...actual, requestJson }
})

const { lookupUserByEmail, userAdminErrorMessage } =
  await import('../src/api/users')
const { accessSaveErrorMessage, shareEmailNotice } =
  await import('../src/api/dossiers')
const { ApiError } = await import('../src/api/client')

const ALICE = {
  id: 'u1',
  email: 'alice@congty.vn',
  display_name: 'Alice',
  role: 'REVIEWER',
}
const NOT_FOUND =
  'Không tìm thấy email này trong đơn vị của bạn, hoặc người này chưa kích hoạt tài khoản. Vui lòng kiểm tra lại.'

describe('lookupUserByEmail (GET /users/lookup, v4.0.0)', () => {
  beforeEach(() => requestJson.mockReset())

  it('asks for the exact email and returns the tenant member', async () => {
    requestJson.mockResolvedValueOnce({ data: ALICE })

    await expect(lookupUserByEmail(' alice@congty.vn ')).resolves.toEqual(ALICE)
    const path = requestJson.mock.calls[0]?.[0] as string
    expect(path).toBe('/api/v1/users/lookup?email=alice%40congty.vn')
  })

  it('returns null on 404 user_not_found', async () => {
    requestJson.mockRejectedValueOnce(
      new ApiError(404, 'Không tìm thấy người dùng.', 'user_not_found'),
    )

    await expect(lookupUserByEmail('ghost@congty.vn')).resolves.toBe(null)
  })

  it('lets other errors through, so the page says it could not check', async () => {
    requestJson.mockRejectedValueOnce(
      new ApiError(503, 'down', 'keycloak_unavailable'),
    )

    await expect(lookupUserByEmail('alice@congty.vn')).rejects.toBeInstanceOf(
      ApiError,
    )
  })
})

describe('accessSaveErrorMessage (PUT /access, v4.0.0)', () => {
  it('names the rejected emails', () => {
    expect(
      accessSaveErrorMessage(
        // requestJson đưa cả body lỗi vào details.
        new ApiError(422, NOT_FOUND, 'share_recipient_not_found', {
          error: {
            code: 'share_recipient_not_found',
            message: NOT_FOUND,
            details: { rejected_emails: ['ghost@congty.vn'] },
          },
        }),
      ),
    ).toBe(`${NOT_FOUND} (ghost@congty.vn)`)
  })

  it('says nothing was saved when Keycloak does not answer', () => {
    expect(
      accessSaveErrorMessage(
        new ApiError(503, 'Keycloak unavailable', 'keycloak_unavailable'),
      ),
    ).toContain('Chưa lưu gì')
  })
})

describe('accessSaveErrorMessage: share_recipient_undeliverable (v5.0.0)', () => {
  it('names the recipient whose domain receives no mail', () => {
    expect(
      accessSaveErrorMessage(
        new ApiError(422, 'x', 'share_recipient_undeliverable', {
          error: {
            code: 'share_recipient_undeliverable',
            details: { rejected_emails: ['operator@ci.local'] },
          },
        }),
      ),
    ).toBe(
      'Không gửi được email tới operator@ci.local vì không tìm thấy email này.',
    )
  })
})

describe('shareEmailNotice (PUT /access, v5.0.0)', () => {
  it('says nothing when every recipient got mail', () => {
    expect(shareEmailNotice([])).toBeNull()
    expect(shareEmailNotice(undefined)).toBeNull()
  })

  it('says the email was not found on a domain that receives no mail', () => {
    expect(
      shareEmailNotice([
        { email: 'operator@ci.local', reason: 'undeliverable' },
      ]),
    ).toBe(
      'Không gửi được email tới operator@ci.local vì không tìm thấy email này.',
    )
  })

  it('says who was not shared with because the mail failed', () => {
    expect(
      shareEmailNotice([
        { email: 'alice@congty.vn', reason: 'send_failed' },
        { email: 'bob@congty.vn', reason: 'send_failed' },
      ]),
    ).toBe(
      'Không gửi được email tới alice@congty.vn, bob@congty.vn vì máy chủ email bị lỗi, vui lòng thử lại sau.',
    )
  })
})

describe('userAdminErrorMessage', () => {
  it('explains an email on a domain that receives no mail', () => {
    expect(
      userAdminErrorMessage(
        new ApiError(422, 'x', 'email_domain_undeliverable'),
      ),
    ).toBe('Tên miền email không nhận được thư, vui lòng kiểm tra lại.')
  })
})
