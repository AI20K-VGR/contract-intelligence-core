<#import "template.ftl" as layout>
<#--
  Link trong thư (đặt mật khẩu / đặt lại mật khẩu) chỉ dùng được một lần và có hạn.
  Mở lại link cũ thì Keycloak báo "Hành động đã hết hạn": nói rõ cho người dùng và
  đưa về trang đăng nhập của app (properties.appUrl, ?sso=1 mở Keycloak luôn).
-->
<#assign expiredLink = message?has_content && (
    message.summary == msg("expiredActionMessage")
    || message.summary == msg("expiredActionTokenNoSessionMessage")
    || message.summary == msg("expiredActionTokenSessionExistsMessage")
)>
<#assign appUrl = (properties.appUrl)!''>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        <#if expiredLink>
            Link đã hết hiệu lực
        <#else>
            Không thể tiếp tục
        </#if>
    <#elseif section = "form">
        <#if expiredLink>
            <p class="lexis-note">Link trong email chỉ dùng được một lần và có thời hạn.</p>
            <p class="lexis-body-text">Nếu bạn đã đặt mật khẩu, hãy đăng nhập. Nếu chưa, hãy nhờ quản trị viên gửi lại email mời.</p>
            <#if appUrl?has_content>
                <a class="lexis-submit" href="${appUrl}?sso=1">Đăng nhập</a>
            <#elseif url.loginUrl?has_content>
                <a class="lexis-submit" href="${url.loginUrl}">Đăng nhập</a>
            </#if>
        <#else>
            <#-- Also shown when the reset-credentials flow denies an ADMINISTRATOR (Deny access authenticator). -->
            <p class="lexis-note">${kcSanitize(message.summary)?no_esc}</p>
            <#if appUrl?has_content>
                <a class="lexis-submit" href="${appUrl}">Quay lại đăng nhập</a>
            <#elseif url.loginUrl?has_content>
                <a class="lexis-submit" href="${url.loginUrl}">Quay lại đăng nhập</a>
            </#if>
            <#if client?? && client.baseUrl?has_content>
                <p class="lexis-back"><a class="lexis-link" href="${client.baseUrl}">Quay lại ứng dụng</a></p>
            </#if>
        </#if>
    </#if>
</@layout.registrationLayout>
