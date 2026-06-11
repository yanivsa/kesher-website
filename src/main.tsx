import React from 'react'
import { createRoot, hydrateRoot } from 'react-dom/client'
import App from './App'
import './styles/index.css'

const app = (
  <React.StrictMode>
    <App />
  </React.StrictMode>
)

const root = document.getElementById('root')!
if (root.hasChildNodes()) {
  hydrateRoot(root, app)
} else {
  createRoot(root).render(app)
}
