<#import "template.ftl" as layout>
<#-- Câu nhắc "You need to change your password…" (warning) của Keycloak trông như lỗi:
     chỉ hiện khung khi là lỗi thật, lời nhắc thay bằng dòng chữ thường bên dưới. -->
<@layout.registrationLayout displayMessage=(!messagesPerField.existsError('password','password-confirm') && message?has_content && message.type == 'error'); section>
    <#if section = "header">
        Đặt mật khẩu
    <#elseif section = "form">
        <p class="lexis-note">Bạn cần đặt mật khẩu mới để kích hoạt tài khoản.</p>
        <script>
            // Email này được điền sẵn ở bước đăng nhập ngay sau khi đặt mật khẩu (info.ftl).
            (function (hint) {
                try { if (hint) sessionStorage.setItem('lexis-login-hint', hint); } catch (e) {}
            })('${((auth.attemptedUsername)!'')?js_string?no_esc}');
        </script>
        <form id="kc-passwd-update-form" class="lexis-form" action="${url.loginAction}" method="post">
            <div class="lexis-field">
                <label class="lexis-label" for="password-new">Mật khẩu mới</label>
                <div class="lexis-input-wrap">
                    <input
                        type="password"
                        id="password-new"
                        name="password-new"
                        class="lexis-input"
                        autofocus
                        autocomplete="new-password"
                        aria-invalid="<#if messagesPerField.existsError('password','password-confirm')>true</#if>"
                    />
                    <button type="button" class="lexis-password-toggle" data-password-toggle aria-label="Hiện mật khẩu" aria-pressed="false">
                        <svg class="lexis-eye-show" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
                        <svg class="lexis-eye-hide" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18"/><path d="M10.6 5.1A10.6 10.6 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.2 4.1M6.6 6.6A17.4 17.4 0 0 0 2 12s3.6 7 10 7a9.7 9.7 0 0 0 5.4-1.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>
                    </button>
                </div>
                <#if messagesPerField.existsError('password')>
                    <p class="lexis-field-error">${kcSanitize(messagesPerField.get('password'))?no_esc}</p>
                </#if>
            </div>

            <div class="lexis-field">
                <label class="lexis-label" for="password-confirm">Xác nhận mật khẩu</label>
                <div class="lexis-input-wrap">
                    <input
                        type="password"
                        id="password-confirm"
                        name="password-confirm"
                        class="lexis-input"
                        autocomplete="new-password"
                        aria-invalid="<#if messagesPerField.existsError('password-confirm')>true</#if>"
                    />
                    <button type="button" class="lexis-password-toggle" data-password-toggle aria-label="Hiện mật khẩu" aria-pressed="false">
                        <svg class="lexis-eye-show" viewBox="0 0 24 24" aria-hidden="true"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>
                        <svg class="lexis-eye-hide" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 3l18 18"/><path d="M10.6 5.1A10.6 10.6 0 0 1 12 5c6.4 0 10 7 10 7a17.6 17.6 0 0 1-3.2 4.1M6.6 6.6A17.4 17.4 0 0 0 2 12s3.6 7 10 7a9.7 9.7 0 0 0 5.4-1.6"/><path d="M9.9 9.9a3 3 0 0 0 4.2 4.2"/></svg>
                    </button>
                </div>
                <#if messagesPerField.existsError('password-confirm')>
                    <p class="lexis-field-error">${kcSanitize(messagesPerField.get('password-confirm'))?no_esc}</p>
                </#if>
            </div>

            <button class="lexis-submit" name="login" id="kc-login" type="submit">
                <span>Đặt mật khẩu</span>
                <span class="material-symbols-outlined">arrow_forward</span>
            </button>
        </form>
    </#if>
</@layout.registrationLayout>
