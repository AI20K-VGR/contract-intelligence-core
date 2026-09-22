export type AppRole = 'admin' | 'user'

export type SessionUser = {
  role: AppRole
  name: string
  email: string
}

export type LoginResult =
  { ok: true; user: SessionUser } | { ok: false; message: string }

export function homePath(role: AppRole) {
  return role === 'admin' ? '/tong-quan' : '/ho-so-cua-toi'
}

export function dossiersPath(role: AppRole) {
  return role === 'admin' ? '/ho-so' : '/ho-so-cua-toi'
}

export function dossiersLabel(role: AppRole) {
  return role === 'admin' ? 'Hồ sơ' : 'Hồ sơ của tôi'
}

export const DEMO_USERS: Record<AppRole, SessionUser> = {
  admin: {
    role: 'admin',
    name: 'Nguyễn Văn Cường',
    email: 'cuong.nguyen@apexlaw.vn',
  },
  user: {
    role: 'user',
    name: 'Trần Thị Mai',
    email: 'mai.tran@apexlaw.vn',
  },
}

const DEMO_ALIASES: Record<string, AppRole> = {
  'cuong.nguyen@apexlaw.vn': 'admin',
  'admin@apexlaw.vn': 'admin',
  'mai.tran@apexlaw.vn': 'user',
  'user@apexlaw.vn': 'user',
}

const ALLOWED_DOMAIN = 'apexlaw.vn'

function displayNameFromEmail(email: string) {
  const local = email.split('@')[0] ?? email
  return local
    .split(/[._-]/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

export function resolveEmailLogin(rawEmail: string): LoginResult {
  const email = rawEmail.trim().toLowerCase()
  if (!email) {
    return { ok: false, message: 'Nhập email doanh nghiệp để tiếp tục.' }
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return { ok: false, message: 'Email không đúng định dạng.' }
  }

  const domain = email.split('@')[1]
  if (domain !== ALLOWED_DOMAIN) {
    return {
      ok: false,
      message: `Chỉ chấp nhận email @${ALLOWED_DOMAIN} (SSO doanh nghiệp).`,
    }
  }

  const aliasRole = DEMO_ALIASES[email]
  if (aliasRole) {
    return { ok: true, user: { ...DEMO_USERS[aliasRole], email } }
  }

  return {
    ok: true,
    user: {
      role: 'user',
      name: displayNameFromEmail(email),
      email,
    },
  }
}

const SESSION_KEY = 'lexis-session'

export function loadSession(): SessionUser | null {
  const raw = sessionStorage.getItem(SESSION_KEY)
  if (!raw) return null

  try {
    const parsed = JSON.parse(raw) as SessionUser
    if (
      (parsed.role === 'admin' || parsed.role === 'user') &&
      parsed.email &&
      parsed.name
    ) {
      return parsed
    }
    return null
  } catch {
    return null
  }
}

export function saveSession(user: SessionUser) {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(user))
}

export function clearSession() {
  sessionStorage.removeItem(SESSION_KEY)
}

export function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}
