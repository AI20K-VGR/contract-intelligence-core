<#ftl output_format="plainText">
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
Lexis Contract Intelligence

<#if shareName?has_content>
Bạn được chia sẻ tài liệu

Bạn đã được ${shareSender?has_content?then(shareSender, "một người dùng")} chia sẻ tài liệu ${shareName}. Bạn vui lòng đăng nhập để xem.
<#else>
Đặt mật khẩu

Quản trị viên đã tạo tài khoản cho bạn. Đặt mật khẩu để đăng nhập.
</#if>

${link}

Liên kết có hiệu lực trong ${expiration}. Nếu bạn không yêu cầu thư này, hãy bỏ qua.
