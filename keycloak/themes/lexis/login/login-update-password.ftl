<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('password','password-confirm'); section>
    <#if section = "header">
        Đặt mật khẩu
    <#elseif section = "subtitle">
        Chọn mật khẩu để kích hoạt tài khoản
    <#elseif section = "form">
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
                    <span class="material-symbols-outlined lexis-input-icon">lock</span>
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
                    <span class="material-symbols-outlined lexis-input-icon">lock</span>
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
