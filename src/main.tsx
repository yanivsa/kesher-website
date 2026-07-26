import React from 'react'
import { createRoot, hydrateRoot } from 'react-dom/client'
import App, { preloadRoute } from './App'
import { shouldHydrateRoute } from './lib/hydration'
import './styles/index.css'

const app = (
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

const root = document.getElementById('root')!

preloadRoute(window.location.pathname).then(() => {
  const canonicalHref = document.querySelector<HTMLLinkElement>('link[rel="canonical"]')?.href;
  if (shouldHydrateRoute(window.location.pathname, canonicalHref, root.hasChildNodes())) {
    hydrateRoot(root, app)
  } else {
    root.replaceChildren()
    createRoot(root).render(app)
  }
})
