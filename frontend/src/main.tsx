import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from '@/App'

const mountId = import.meta.env.VITE_MOUNT_ID || 'agicent-consultant-root'
const root =
  document.getElementById(mountId) ??
  document.getElementById('root')

if (!root) {
  throw new Error(
    `Mount element not found. Add <div id="${mountId}"></div> to the host page.`,
  )
}

root.setAttribute('data-agicent-consultant', 'true')

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
