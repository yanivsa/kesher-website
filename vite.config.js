import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react-swc'

const consentRegionPreview = () => ({
  name: 'consent-region-preview',
  configurePreviewServer(server) {
    server.middlewares.use((request, response, next) => {
      if (request.url?.split('?')[0] !== '/api/consent-region') return next()

      // Cloudflare Pages supplies the real visitor country in production.
      // Vite preview has no request.cf context, so keep local/E2E behavior
      // privacy-safe and deterministic instead of producing a console 404.
      response.statusCode = 200
      response.setHeader('Content-Type', 'application/json; charset=utf-8')
      response.setHeader('Cache-Control', 'no-store')
      response.end(JSON.stringify({ requiresConsent: true }))
    })
  },
})

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), consentRegionPreview()],
})
