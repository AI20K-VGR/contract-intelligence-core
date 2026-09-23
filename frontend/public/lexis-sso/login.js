function paintLexisLogin() {
  document.documentElement.classList.remove('pf-v5-theme-dark')
  document.title = 'Lexis Contract Intelligence'

  const form = document.getElementById('kc-form-login')
  if (!form || form.dataset.lexis === '1') return
  form.dataset.lexis = '1'

  const header = document.querySelector('.pf-v5-c-login__main-header')
  if (header && !header.querySelector('.lexis-brand')) {
    header.insertAdjacentHTML(
      'afterbegin',
      `<div class="lexis-brand"><svg class="lexis-brand-mark" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3zm0 2.2 6 2.2v4.5c0 4-2.6 7.6-6 9.1-3.4-1.5-6-5.1-6-9.1V6.4l6-2.2z"/></svg><span>Lexis Contract Intelligence</span></div>`,
    )
  }

  const title = document.getElementById('kc-page-title')
  if (title) title.textContent = 'Đăng nhập'
  if (title && !header?.querySelector('.lexis-subtitle')) {
    title.insertAdjacentHTML(
      'afterend',
      '<p class="lexis-subtitle">Truy cập không gian làm việc của bạn</p>',
    )
  }

  form.insertAdjacentHTML(
    'afterbegin',
    `<ol class="lexis-steps" aria-label="Tiến trình đăng nhập">
      <li class="lexis-step lexis-step-done"><span class="lexis-step-index">✓</span><span>Email</span></li>
      <li class="lexis-step-line" aria-hidden="true"></li>
      <li class="lexis-step lexis-step-current" aria-current="step"><span class="lexis-step-index">2</span><span>Mật khẩu</span></li>
    </ol>`,
  )

  const usernameLabel = document.querySelector('label[for="username"] .pf-v5-c-form__label-text')
  if (usernameLabel) usernameLabel.textContent = 'Email hoặc tên đăng nhập'
  const passwordLabel = document.querySelector('label[for="password"] .pf-v5-c-form__label-text')
  if (passwordLabel) passwordLabel.textContent = 'Mật khẩu'

  const remember = document.querySelector('label[for="rememberMe"] .pf-v5-c-check__label')
  if (remember) remember.textContent = 'Ghi nhớ đăng nhập'
  const forgot = document.querySelector('.pf-v5-c-helper-text a')
  if (forgot) forgot.textContent = 'Quên mật khẩu?'

  const submit = document.getElementById('kc-login')
  if (submit) submit.textContent = 'Đăng nhập'

  if (!document.querySelector('.lexis-sso-footer')) {
    const footer = document.createElement('footer')
    footer.className = 'lexis-sso-footer'
    footer.innerHTML =
      '<span>Chính sách bảo mật · Điều khoản sử dụng</span><span>© 2025 Lexis Contract Intelligence</span>'
    document.body.append(footer)
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', paintLexisLogin)
} else {
  paintLexisLogin()
}
