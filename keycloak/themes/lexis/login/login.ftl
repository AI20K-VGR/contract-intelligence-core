<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=!messagesPerField.existsError('username','password'); section>
    <#if section = "header">
        Đăng nhập
    <#elseif section = "subtitle">
        Truy cập không gian làm việc của bạn
    <#elseif section = "form">
        <#if realm.password>
            <form id="kc-form-login" class="lexis-form" onsubmit="login.disabled = true; return true;" action="${url.loginAction}" method="post">
                <ol class="lexis-steps" aria-label="Tiến trình đăng nhập">
                    <li class="lexis-step lexis-step-done">
                        <span class="lexis-step-index" aria-hidden="true">
                            <span class="material-symbols-outlined">check</span>
                        </span>
                        <span class="lexis-step-label">Email</span>
                    </li>
                    <li class="lexis-step-line" aria-hidden="true"></li>
                    <li class="lexis-step lexis-step-current" aria-current="step">
                        <span class="lexis-step-index" aria-hidden="true">2</span>
                        <span class="lexis-step-label">Mật khẩu</span>
                    </li>
                </ol>
                <div class="lexis-field">
                    <label class="lexis-label" for="username">
                        <#if !realm.loginWithEmailAllowed>
                            ${msg("username")}
                        <#elseif !realm.registrationEmailAsUsername>
                            Email hoặc tên đăng nhập
                        <#else>
                            Email doanh nghiệp
                        </#if>
                    </label>
                    <div class="lexis-input-wrap">
                        <input
                            tabindex="1"
                            id="username"
                            class="lexis-input"
                            name="username"
                            value="${(login.username!'')}"
                            type="text"
                            autofocus
                            autocomplete="username"
                            placeholder="admin@ci.local"
                            aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>"
                        />
                        <span class="material-symbols-outlined lexis-input-icon">domain</span>
                    </div>
                    <#if messagesPerField.existsError('username','password')>
                        <p class="lexis-field-error">${kcSanitize(messagesPerField.getFirstError('username','password'))?no_esc}</p>
                    </#if>
                </div>

                <div class="lexis-field">
                    <label class="lexis-label" for="password">Mật khẩu</label>
                    <div class="lexis-input-wrap">
                        <input
                            tabindex="2"
                            id="password"
                            class="lexis-input"
                            name="password"
                            type="password"
                            autocomplete="current-password"
                            aria-invalid="<#if messagesPerField.existsError('username','password')>true</#if>"
                        />
                        <span class="material-symbols-outlined lexis-input-icon">lock</span>
                    </div>
                </div>

                <div class="lexis-row">
                    <#if realm.rememberMe && !usernameHidden??>
                        <label class="lexis-check">
                            <input tabindex="3" id="rememberMe" name="rememberMe" type="checkbox" <#if login.rememberMe??>checked</#if>>
                            <span>Ghi nhớ đăng nhập</span>
                        </label>
                    <#else>
                        <span></span>
                    </#if>
                    <#if realm.resetPasswordAllowed>
                        <a tabindex="4" class="lexis-link" href="${url.loginResetCredentialsUrl}">Quên mật khẩu?</a>
                    </#if>
                </div>

                <input type="hidden" id="id-hidden-input" name="credentialId" <#if auth.selectedCredential?has_content>value="${auth.selectedCredential}"</#if>/>

                <button tabindex="5" class="lexis-submit" name="login" id="kc-login" type="submit">
                    <span>Đăng nhập</span>
                    <span class="material-symbols-outlined">arrow_forward</span>
                </button>
            </form>
        </#if>
    </#if>
</@layout.registrationLayout>
