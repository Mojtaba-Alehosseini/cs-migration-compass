import { execFileSync } from 'node:child_process'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// BASE_PATH is set by the Pages workflow to "/<repo>/" so the built site works
// from a project page. Locally and on a custom domain it stays "/".
const base = process.env.BASE_PATH ?? '/'

/* #70 -- the site names repository files to its readers, so those names are
 * links. Both halves of the link are decided HERE rather than written into a
 * tracked file, for the same reason: a commit baked into a source file dirties
 * that file on every commit.
 *
 * The ref is a COMMIT, not a branch. `blob/main/data/salary_es.json` is a
 * promise about a moving target -- the line a card cites drifts, and the file
 * can be renamed out from under every link the site has ever published. A SHA
 * cannot. In CI, GITHUB_SHA is the commit being built and is by definition
 * pushed; locally, HEAD may not be pushed yet, so a local build falls back to
 * `main` rather than producing links that 404 until someone pushes.
 */
function gitOut(args: string[]): string {
  try {
    return execFileSync('git', args, { encoding: 'utf8' }).trim()
  } catch {
    return ''
  }
}

const repoRef = process.env.GITHUB_SHA || gitOut(['rev-parse', 'HEAD'])
const pushed = repoRef && gitOut(['branch', '--remotes', '--contains', repoRef])
const ref = process.env.GITHUB_SHA || (pushed ? repoRef : 'main')

/* GITHUB_REPOSITORY in CI; the origin remote otherwise -- so a fork's copy of
 * the site links into the fork, not into this repository. */
const slug = process.env.GITHUB_REPOSITORY
  || (gitOut(['remote', 'get-url', 'origin']).match(/github\.com[/:]([^/]+\/[^/.]+)/)?.[1] ?? '')
const blobBase = slug ? `https://github.com/${slug}/blob/${ref}/` : ''

export default defineConfig({
  base,
  define: { __REPO_BLOB_BASE__: JSON.stringify(blobBase) },
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  build: {
    target: 'es2022',
    // History series are large; splitting keeps the first paint small so a
    // visitor arriving from a Reddit link sees data before they bounce.
    rollupOptions: {
      output: {
        manualChunks: {
          motion: ['motion'],
          router: ['react-router-dom'],
        },
      },
    },
  },
})
