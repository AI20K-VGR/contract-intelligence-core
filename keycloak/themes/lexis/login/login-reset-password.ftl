<#import "template.ftl" as layout>
<@layout.registrationLayout displayInfo=true; section>
    <#if section = "header">
        Đặt lại mật khẩu
    <#elseif section = "form">
        <form id="kc-reset-password-form" class="lexis-form" action="${url.loginAction}" method="post">
            <div class="lexis-field">
                <label class="lexis-label" for="username">Email hoặc tên đăng nhập</label>
                <div class="lexis-input-wrap">
                    <input
                        type="text"
                        id="username"
                        name="username"
                        class="lexis-input"
                        autofocus
                        value="${(auth.attemptedUsername!'')}"
                        placeholder="admin@ci.local"
                    />
                    <span class="material-symbols-outlined lexis-input-icon">domain</span>
                </div>
            </div>
            <button class="lexis-submit" type="submit">
                <span>Gửi hướng dẫn</span>
                <span class="material-symbols-outlined">arrow_forward</span>
            </button>
            <p class="lexis-back">
                <a class="lexis-link" href="${url.loginUrl}">Quay lại đăng nhập</a>
            </p>
        </form>
    <#elseif section = "info">
        Nhập email tài khoản. Keycloak sẽ gửi hướng dẫn đặt lại mật khẩu nếu tài khoản tồn tại.
    </#if>
</@layout.registrationLayout>
