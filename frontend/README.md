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
