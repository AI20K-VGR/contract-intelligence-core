<#import "template.ftl" as layout>
<#--
  Bước VERIFY_PROFILE: Keycloak bắt bổ sung các trường bắt buộc còn thiếu (thường là
  Họ). Viết lại bằng tiếng Việt; trường còn thiếu là lời nhắc chữ thường, không phải lỗi đỏ.
-->
<#assign fieldLabels = {"username": "Tên đăng nhập", "email": "Email", "firstName": "Tên", "lastName": "Họ"}>
<@layout.registrationLayout displayMessage=messagesPerField.exists('global'); section>
    <#if section = "header">
        Hoàn tất thông tin tài khoản
    <#elseif section = "form">
        <p class="lexis-note">Bổ sung thông tin còn thiếu để vào hệ thống.</p>
        <form id="kc-update-profile-form" class="lexis-form" action="${url.loginAction}" method="post">
            <#list profile.attributes as attribute>
                <#if attribute.name == 'locale'>
                    <#if realm.internationalizationEnabled && locale.currentLanguageTag?has_content>
                        <input type="hidden" name="locale" value="${locale.currentLanguageTag}"/>
                    </#if>
                <#else>
                    <#assign label = (fieldLabels[attribute.name])!(advancedMsg(attribute.displayName!attribute.name))>
                    <#assign value = attribute.value!''>
                    <div class="lexis-field">
                        <label class="lexis-label" for="${attribute.name}">${label}</label>
                        <div class="lexis-input-wrap">
                            <input
                                type="<#if attribute.name == 'email'>email<#else>text</#if>"
                                id="${attribute.name}"
                                name="${attribute.name}"
                                class="lexis-input"
                                value="${value}"
                                <#if attribute.readOnly>readonly</#if>
                                <#if attribute.autocomplete??>autocomplete="${attribute.autocomplete}"</#if>
                                <#if !attribute.readOnly && value == '' && attribute.required>autofocus</#if>
                            />
                        </div>
                        <#if messagesPerField.existsError(attribute.name)>
                            <#if attribute.required && value == ''>
                                <p class="lexis-field-hint">Vui lòng nhập ${label?lower_case}.</p>
                            <#else>
                                <p class="lexis-field-error">${kcSanitize(messagesPerField.get(attribute.name))?no_esc}</p>
                            </#if>
                        </#if>
                    </div>
                </#if>
            </#list>

            <button class="lexis-submit" type="submit">
                <span>Lưu và tiếp tục</span>
                <span class="material-symbols-outlined">arrow_forward</span>
            </button>
        </form>
        <script>
            // Email này được điền sẵn ở bước đăng nhập ngay sau khi xong (info.ftl).
            (function () {
                var email = document.getElementById('email');
                try { if (email && email.value) sessionStorage.setItem('lexis-login-hint', email.value); } catch (e) {}
            })();
        </script>
    </#if>
</@layout.registrationLayout>
