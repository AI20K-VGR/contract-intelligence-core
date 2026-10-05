<#import "template.ftl" as layout>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        Thông tin
    <#elseif section = "form">
        <p class="lexis-body-text">${kcSanitize(message.summary)?no_esc}</p>
        <#if skipLink??>
        <#else>
            <#if pageRedirectUri?has_content>
                <#-- After the password-set e-mail flow: go on to the app's login page. -->
                <meta http-equiv="refresh" content="3;url=${pageRedirectUri}">
                <p class="lexis-body-text">Đang chuyển đến trang đăng nhập...</p>
                <a class="lexis-submit" href="${pageRedirectUri}">Đăng nhập</a>
            <#elseif actionUri?has_content>
                <a class="lexis-submit" href="${actionUri}">Tiếp tục</a>
            <#elseif (client.baseUrl)?has_content>
                <a class="lexis-submit" href="${client.baseUrl}">Quay lại ứng dụng</a>
            </#if>
        </#if>
    </#if>
</@layout.registrationLayout>
