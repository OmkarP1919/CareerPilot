import react from '@vitejs/plugin-react'
import { defineConfig, loadEnv } from 'vite'
import { validateProductionEnv } from './scripts/validateEnv.mjs'

// The API endpoint is configured entirely through VITE_API_BASE_URL (see
// frontend/.env.example). No development proxy is needed because the API
// client always targets an absolute base URL.
//
// During `vite build` (production mode), the environment is validated so the
// bundle never silently points at localhost or leaks a missing-URL build.
export default defineConfig(({ command, mode }) => {
  if (command === 'build' && mode === 'production') {
    const env = loadEnv(mode, process.cwd(), '')
    validateProductionEnv(env)
  }

  return {
    plugins: [react()],
  }
})