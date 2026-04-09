import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: [['babel-plugin-react-compiler']],
      },
    }),
  ],
  
  test: {
    environment: 'jsdom',
    setupFiles: './test/setup.ts',
    globals: true,
    include: ['test/**/*.test.tsx', 'tests/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text'],
      include: ['src/**/*.tsx', 'src/**/*.ts'],
      exclude: ['src/main.tsx']
    }
  }
})
