import { describe, expect, it } from 'vitest'
import { inviteBounceMessage, type ManagedUser } from '../src/api/users'

const invited: ManagedUser = {
  id: 'kc-new',
  email: 'sai.ten@gmail.com',
  display_name: 'Người mới',
  role: 'OPERATOR',
  status: 'invited',
  created_at: '2026-10-20T02:00:00Z',
}

describe('inviteBounceMessage', () => {
  it('says the address was not found when Gmail reports it', () => {
    expect(
      inviteBounceMessage({
        ...invited,
        invite_delivery: 'bounced',
        invite_delivery_reason: 'mailbox_not_found',
      }),
    ).toBe(
      'Không gửi được email mời tới sai.ten@gmail.com vì không tìm thấy địa chỉ này. Kiểm tra lại email và tạo người dùng với địa chỉ đúng.',
    )
  })

  it('says the receiving server refused for any other bounce', () => {
    expect(
      inviteBounceMessage({
        ...invited,
        invite_delivery: 'bounced',
        invite_delivery_reason: 'rejected',
      }),
    ).toContain('máy chủ thư bên nhận từ chối')
  })

  it('has nothing to say while the invite is pending, sent or unknown', () => {
    expect(
      inviteBounceMessage({ ...invited, invite_delivery: 'pending' }),
    ).toBeNull()
    expect(
      inviteBounceMessage({ ...invited, invite_delivery: 'sent' }),
    ).toBeNull()
    expect(inviteBounceMessage(invited)).toBeNull()
  })
})
