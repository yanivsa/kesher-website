import React from 'react'
import { createRoot, hydrateRoot } from 'react-dom/client'
import App, { preloadRoute } from './App'
import './styles/index.css'

const app = (
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

const root = document.getElementById('root')!

preloadRoute(window.location.pathname).then(() => {
  if (root.hasChildNodes()) {
    hydrateRoot(root, app)
  } else {
    createRoot(root).render(app)
  }
})
