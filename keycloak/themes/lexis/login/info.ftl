<#import "template.ftl" as layout>
<#--
  Link trong thư mời mở màn xác nhận "Thực hiện các hành động sau" (có actionUri):
  tự đi tiếp bằng JS, không bắt bấm "Tiếp tục". Chỉ JS mới đi tiếp nên trình quét
  link trong hộp thư không dùng mất link. Đặt mật khẩu xong (accountUpdatedMessage
  + pageRedirectUri) thì về thẳng app với ?sso=1 để app mở đăng nhập ngay.
-->
<#assign accountUpdated = pageRedirectUri?has_content && message?has_content && message.summary == msg("accountUpdatedMessage")>
<#assign confirmActions = !pageRedirectUri?has_content && actionUri?has_content>
<@layout.registrationLayout displayMessage=false; section>
    <#if section = "header">
        <#if accountUpdated>
            Đã đặt mật khẩu
        <#elseif confirmActions>
            Đang chuyển tiếp
        <#else>
            Thông tin
        </#if>
    <#elseif section = "form">
        <#if accountUpdated>
            <p class="lexis-body-text">Đang vào hệ thống...</p>
            <a class="lexis-submit" id="lexis-next" href="${pageRedirectUri}" data-redirect="${pageRedirectUri}" data-sso="true">Vào hệ thống</a>
        <#elseif confirmActions>
            <p class="lexis-body-text">Vui lòng chờ trong giây lát...</p>
            <a class="lexis-submit" id="lexis-next" href="${actionUri}" data-redirect="${actionUri}">Tiếp tục</a>
        <#else>
            <p class="lexis-body-text">${kcSanitize(message.summary)?no_esc}</p>
            <#if skipLink??>
            <#else>
                <#if pageRedirectUri?has_content>
                    <a class="lexis-submit" id="lexis-next" href="${pageRedirectUri}" data-redirect="${pageRedirectUri}">Quay lại ứng dụng</a>
                <#elseif actionUri?has_content>
                    <a class="lexis-submit" href="${actionUri}">Tiếp tục</a>
                <#elseif (client.baseUrl)?has_content>
                    <a class="lexis-submit" href="${client.baseUrl}">Quay lại ứng dụng</a>
                </#if>
            </#if>
        </#if>
        <script>
            (function () {
                var next = document.getElementById('lexis-next');
                if (!next || !next.dataset.redirect) return;
                var target = next.dataset.redirect;
                if (next.dataset.sso) {
                    // Email do trang đặt mật khẩu/cập nhật hồ sơ lưu, để điền sẵn ô đăng nhập.
                    var hint = '';
                    try {
                        hint = sessionStorage.getItem('lexis-login-hint') || '';
                        sessionStorage.removeItem('lexis-login-hint');
                    } catch (e) {}
                    try {
                        var url = new URL(target);
                        url.searchParams.set('sso', '1');
                        if (hint) url.searchParams.set('login_hint', hint);
                        target = url.toString();
                    } catch (e) {}
                    next.href = target;
                }
                window.location.replace(target);
            })();
        </script>
    </#if>
</@layout.registrationLayout>
