<#macro registrationLayout displayInfo=false displayMessage=true displayRequiredFields=false>
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Lexis Contract Intelligence</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200" rel="stylesheet">
    <#if properties.styles?has_content>
        <#list properties.styles?split(" ") as style>
            <link href="${url.resourcesPath}/${style}" rel="stylesheet">
        </#list>
    </#if>
</head>
<body class="lexis-body">
    <div class="lexis-grid" aria-hidden="true"></div>

    <header class="lexis-header"></header>

    <main class="lexis-main">
        <div class="lexis-card">
            <div class="lexis-card-accent"></div>

            <div class="lexis-brand">
                <span class="material-symbols-outlined lexis-brand-icon">shield</span>
                <span class="lexis-brand-text">LEXIS CONTRACT INTELLIGENCE</span>
            </div>

            <div class="lexis-heading">
                <h1>
                    <#nested "header">
                </h1>
                <p class="lexis-subtitle"><#nested "subtitle"></p>
            </div>

            <#if displayMessage && message?has_content && (message.type != 'warning' || !isAppInitiatedAction??)>
                <div class="lexis-alert lexis-alert-${message.type}">
                    ${kcSanitize(message.summary)?no_esc}
                </div>
            </#if>

            <#nested "form">

            <#if displayInfo>
                <div class="lexis-info">
                    <#nested "info">
                </div>
            </#if>
        </div>
    </main>

    <footer class="lexis-footer">
        <div class="lexis-footer-inner">
            <div class="lexis-footer-links">
                <span>Chính sách bảo mật</span>
                <span class="lexis-dot">•</span>
                <span>Điều khoản sử dụng</span>
            </div>
            <span>© 2025 Lexis Contract Intelligence. All rights reserved.</span>
        </div>
    </footer>
</body>
</html>
</#macro>
