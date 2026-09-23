<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        Thông tin
    <#elseif section = "form">
        <p class="lexis-body-text">${kcSanitize(message.summary)?no_esc}</p>
        <#if skipLink??>
        <#else>
            <#if pageRedirectUri?has_content>
                <p class="lexis-back"><a class="lexis-link" href="${pageRedirectUri}">Quay lại ứng dụng</a></p>
            <#elseif actionUri?has_content>
                <p class="lexis-back"><a class="lexis-link" href="${actionUri}">Tiếp tục</a></p>
            <#elseif (client.baseUrl)?has_content>
                <p class="lexis-back"><a class="lexis-link" href="${client.baseUrl}">Quay lại ứng dụng</a></p>
            </#if>
        </#if>
    </#if>
</@layout.registrationLayout>
