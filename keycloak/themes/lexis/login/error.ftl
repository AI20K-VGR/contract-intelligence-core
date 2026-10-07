<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
    <#if section = "header">
        Không thể tiếp tục
    <#elseif section = "form">
        <#-- Also shown when the reset-credentials flow denies an ADMINISTRATOR (Deny access authenticator). -->
        <p class="lexis-body-text">${kcSanitize(message.summary)?no_esc}</p>
        <#if url.loginUrl?has_content>
            <a class="lexis-submit" href="${url.loginUrl}">Quay lại đăng nhập</a>
        </#if>
        <#if client?? && client.baseUrl?has_content>
            <p class="lexis-back"><a class="lexis-link" href="${client.baseUrl}">Quay lại ứng dụng</a></p>
        </#if>
    </#if>
</@layout.registrationLayout>
