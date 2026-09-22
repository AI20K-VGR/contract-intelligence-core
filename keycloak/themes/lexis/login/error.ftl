<#import "template.ftl" as layout>
<@layout.registrationLayout; section>
    <#if section = "header">
        Không thể hoàn tất đăng nhập
    <#elseif section = "form">
        <p class="lexis-body-text">${kcSanitize(message.summary)?no_esc}</p>
        <#if client?? && client.baseUrl?has_content>
            <p class="lexis-back"><a class="lexis-link" href="${client.baseUrl}">Quay lại ứng dụng</a></p>
        <#else>
            <p class="lexis-back"><a class="lexis-link" href="${url.loginUrl}">Quay lại đăng nhập</a></p>
        </#if>
    </#if>
</@layout.registrationLayout>
