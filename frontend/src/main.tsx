import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { ViewProvider } from './state/view'
import { FramesProvider } from './state/frames'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ViewProvider>
      <FramesProvider>
        <App />
      </FramesProvider>
    </ViewProvider>
  </StrictMode>,
)
