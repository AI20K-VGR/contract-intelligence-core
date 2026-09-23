import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv, type ProxyOptions } from 'vite'

const keycloakProxyPrefix = '/keycloak'

function keycloakDevProxy(target: string): ProxyOptions {
  const upstream = target.replace(/\/$/, '')
  const upstreamHosts = [upstream, upstream.replace(/^https:/, 'http:')]

  return {
    target: upstream,
    changeOrigin: true,
    secure: true,
    rewrite: (path) => path.replace(new RegExp(`^${keycloakProxyPrefix}`), '') || '/',
    selfHandleResponse: true,
    configure: (proxy) => {
      proxy.on('proxyReq', (proxyReq) => {
        proxyReq.setHeader('Bypass-Tunnel-Reminder', 'true')
      })
      proxy.on('proxyRes', (proxyRes, req, res) => {
        const chunks: Buffer[] = []
        proxyRes.on('data', (chunk: Buffer) => {
          chunks.push(chunk)
        })
        proxyRes.on('end', () => {
          const type = String(proxyRes.headers['content-type'] ?? '')
          const textual =
            type.includes('json') ||
            type.includes('text') ||
            type.includes('javascript') ||
            type.includes('xml')
          let body = Buffer.concat(chunks)
          const host = req.headers.host ?? 'localhost:5173'
          const localBase = `http://${host}${keycloakProxyPrefix}`
          if (textual) {
            let text = body.toString('utf8')
            for (const hostUrl of upstreamHosts) {
              text = text.split(hostUrl).join(localBase)
            }
            text = text
              .replaceAll('"/realms/', '"/keycloak/realms/')
              .replaceAll("'/realms/", "'/keycloak/realms/")
              .replaceAll('"/resources/', '"/keycloak/resources/')
              .replaceAll("'/resources/", "'/keycloak/resources/")
              .replaceAll('=/realms/', '=/keycloak/realms/')
            if (
              text.includes('id="kc-form-login"') &&
              !text.includes('/lexis-sso/login.css')
            ) {
              text = text.replace(
                '</head>',
                '<link rel="preconnect" href="https://fonts.googleapis.com" />' +
                  '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />' +
                  '<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />' +
                  '<link rel="stylesheet" href="/lexis-sso/login.css" />' +
                  '<script src="/lexis-sso/login.js" defer></script></head>',
              )
            }
            body = Buffer.from(text)
          }

          const headers = { ...proxyRes.headers }
          delete headers['content-length']
          if (headers.location) {
            let location = String(headers.location)
            for (const hostUrl of upstreamHosts) {
              location = location.split(hostUrl).join(localBase)
            }
            if (location.startsWith('/realms/') || location.startsWith('/resources/')) {
              location = `${keycloakProxyPrefix}${location}`
            }
            headers.location = location
          }
          const cookies = headers['set-cookie']
          if (cookies) {
            const list = Array.isArray(cookies) ? cookies : [cookies]
            headers['set-cookie'] = list.map((cookie) =>
              cookie
                .replace(/;\s*Domain=[^;]*/gi, '')
                .replace(/;\s*Secure/gi, '')
                .replace(/;\s*SameSite=None/gi, '; SameSite=Lax')
                .replace(/;\s*Path=\/realms/gi, '; Path=/keycloak/realms')
                .replace(/;\s*Path=\/resources/gi, '; Path=/keycloak/resources'),
            )
          }
          res.writeHead(proxyRes.statusCode ?? 502, headers)
          res.end(body)
        })
      })
    },
  }
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const keycloakUrl = env.VITE_KEYCLOAK_URL?.replace(/\/$/, '') ?? ''
  const proxy =
    keycloakUrl.includes('loca.lt')
      ? { [keycloakProxyPrefix]: keycloakDevProxy(keycloakUrl) }
      : undefined

  return {
    plugins: [react(), tailwindcss()],
    server: { proxy },
  }
})
