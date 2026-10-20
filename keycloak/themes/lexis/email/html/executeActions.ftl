<#import "template.ftl" as layout>
<#assign expiration = linkExpirationFormatter(linkExpiration)>
<#function attrValue key>
    <#if !(user?? && user.attributes?? && user.attributes[key]??)>
        <#return "">
    </#if>
    <#local raw = user.attributes[key]>
    <#if raw?is_sequence && !raw?is_string>
        <#return raw?first!"">
    </#if>
    <#return raw?string>
</#function>
<#assign shareName = attrValue("share_dossier_name")>
<#assign shareSender = attrValue("share_sender_name")>
<@layout.emailLayout>
    <#if shareName?has_content>
        <h1 style="margin:0 0 8px;font-size:18px;line-height:24px;font-weight:600;color:#0b1c30;">Bạn được chia sẻ tài liệu</h1>
        <p style="margin:0 0 24px;font-size:14px;line-height:20px;color:#545f73;">Bạn đã được ${shareSender?has_content?then(shareSender, "một người dùng")} chia sẻ tài liệu ${shareName}. Bạn vui lòng đăng nhập để xem.</p>
    <#else>
        <h1 style="margin:0 0 8px;font-size:18px;line-height:24px;font-weight:600;color:#0b1c30;">Đặt mật khẩu</h1>
        <p style="margin:0 0 24px;font-size:14px;line-height:20px;color:#545f73;">Quản trị viên đã tạo tài khoản cho bạn. Đặt mật khẩu để đăng nhập.</p>
    </#if>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
        <tr>
            <td align="center" style="background-color:#0b1f3a;border-radius:4px;">
                <a href="${link}" style="display:block;padding:12px 24px;font-family:'IBM Plex Sans',Arial,Helvetica,sans-serif;font-size:15px;line-height:20px;font-weight:600;color:#ffffff;text-decoration:none;">${shareName?has_content?then("Đăng nhập", "Đặt mật khẩu")}</a>
            </td>
        </tr>
    </table>
    <p style="margin:0 0 8px;font-size:12px;line-height:16px;color:#545f73;">Liên kết có hiệu lực trong ${expiration}. Nếu bạn không yêu cầu thư này, hãy bỏ qua.</p>
    <p style="margin:0;font-size:12px;line-height:16px;color:#75777e;word-break:break-all;">${link}</p>
</@layout.emailLayout>
