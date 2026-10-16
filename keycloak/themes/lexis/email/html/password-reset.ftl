<#import "template.ftl" as layout>
<#assign expiration = linkExpirationFormatter(linkExpiration)>
<@layout.emailLayout>
    <h1 style="margin:0 0 8px;font-size:18px;line-height:24px;font-weight:600;color:#0b1c30;">Đặt lại mật khẩu</h1>
    <p style="margin:0 0 24px;font-size:14px;line-height:20px;color:#545f73;">Bạn vừa yêu cầu đặt lại mật khẩu cho tài khoản Lexis Contract Intelligence. Bấm nút bên dưới để đặt mật khẩu mới.</p>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:0 0 24px;">
        <tr>
            <td align="center" style="background-color:#0b1f3a;border-radius:4px;">
                <a href="${link}" style="display:block;padding:12px 24px;font-family:'IBM Plex Sans',Arial,Helvetica,sans-serif;font-size:15px;line-height:20px;font-weight:600;color:#ffffff;text-decoration:none;">Đặt lại mật khẩu</a>
            </td>
        </tr>
    </table>
    <p style="margin:0 0 8px;font-size:12px;line-height:16px;color:#545f73;">Liên kết có hiệu lực trong ${expiration}. Nếu bạn không yêu cầu đặt lại mật khẩu, hãy bỏ qua thư này, mật khẩu hiện tại vẫn giữ nguyên.</p>
    <p style="margin:0;font-size:12px;line-height:16px;color:#75777e;word-break:break-all;">${link}</p>
</@layout.emailLayout>
