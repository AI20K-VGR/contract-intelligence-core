import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App.tsx'
// Icon font bundled with the app: icons must not depend on a CDN being reachable.
import 'material-symbols/outlined.css'
import './index.css'
import { initPalette } from './theme/palettes'

initPalette()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
