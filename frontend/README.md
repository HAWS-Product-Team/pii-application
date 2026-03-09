# React + TypeScript + Vite

This template provides a minimal setup to get React working in Vite with HMR and some ESLint rules.

Currently, two official plugins are available:

- [@vitejs/plugin-react](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react) uses [Babel](https://babeljs.io/) (or [oxc](https://oxc.rs) when used in [rolldown-vite](https://vite.dev/guide/rolldown)) for Fast Refresh
- [@vitejs/plugin-react-swc](https://github.com/vitejs/vite-plugin-react/blob/main/packages/plugin-react-swc) uses [SWC](https://swc.rs/) for Fast Refresh

## React Compiler

The React Compiler is enabled on this template. See [this documentation](https://react.dev/learn/react-compiler) for more information.

Note: This will impact Vite dev & build performances.

Getting started
---------------

Prerequisites:

- Node.js 18+ (or LTS)
- npm (or yarn / pnpm)

Install dependencies:

```bash
cd frontend
npm install
# or: yarn
# or: pnpm install
```

Run the development server (with HMR):

```bash
npm run dev
# open http://localhost:5173 (or the URL shown in the terminal)
```

Build for production:

```bash
npm run build
```

Preview the production build locally:

```bash
npm run preview
```

Useful scripts
--------------

- `npm run dev` — start Vite dev server
- `npm run build` — produce production build in `dist/`
- `npm run preview` — locally preview the production build
- `npm run lint` — run ESLint (if configured)

Environment
-----------

If the app requires environment variables, place them in a `.env` file at the `frontend/` root. Vite exposes variables prefixed with `VITE_` to the client.

Troubleshooting
---------------

- If ports are in use, change the port by setting `PORT` or use Vite's `--port` flag.
- If TypeScript errors block the dev server, run `npm run build` to see full diagnostics.
- For dependency issues, try removing `node_modules` and reinstalling:

```bash
rm -rf node_modules package-lock.json
npm install
```

Where to look next
------------------

See the source in the `src/` directory for app entry points and components.


## Expanding the ESLint configuration

If you are developing a production application, we recommend updating the configuration to enable type-aware lint rules:

```js
export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...

      // Remove tseslint.configs.recommended and replace with this
      tseslint.configs.recommendedTypeChecked,
      // Alternatively, use this for stricter rules
      tseslint.configs.strictTypeChecked,
      // Optionally, add this for stylistic rules
      tseslint.configs.stylisticTypeChecked,

      // Other configs...
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```

You can also install [eslint-plugin-react-x](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-x) and [eslint-plugin-react-dom](https://github.com/Rel1cx/eslint-react/tree/main/packages/plugins/eslint-plugin-react-dom) for React-specific lint rules:

```js
// eslint.config.js
import reactX from 'eslint-plugin-react-x'
import reactDom from 'eslint-plugin-react-dom'

export default defineConfig([
  globalIgnores(['dist']),
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      // Other configs...
      // Enable lint rules for React
      reactX.configs['recommended-typescript'],
      // Enable lint rules for React DOM
      reactDom.configs.recommended,
    ],
    languageOptions: {
      parserOptions: {
        project: ['./tsconfig.node.json', './tsconfig.app.json'],
        tsconfigRootDir: import.meta.dirname,
      },
      // other options...
    },
  },
])
```
