import { defineConfig } from 'vite'
import { svelte }       from '@sveltejs/vite-plugin-svelte'
import { crx }          from '@crxjs/vite-plugin'
import type { ManifestV3Export } from '@crxjs/vite-plugin'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import _manifest from './manifest.json'
const manifest = _manifest as ManifestV3Export
const rootDir = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  plugins: [
    svelte(),
    crx({ manifest }),
    {
      name: 'copy-autofilled-rules',
      generateBundle() {
        const sourcePath = resolve(rootDir, 'autofilled-rules.json')
        this.emitFile({
          type: 'asset',
          fileName: 'autofilled-rules.json',
          source: readFileSync(sourcePath),
        })
      },
    },
  ],
  server: { port: 5173, strictPort: true },
})
