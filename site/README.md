# Landing page

Static. `public/` is what gets served; `wrangler.jsonc` makes it an assets-only
Cloudflare Worker named `ai-cashier-site`.

    cd site && npx wrangler deploy

The download button points at the GitHub release's `latest/download/` URL, and
the page asks the GitHub API for the current tag, size and date, so it never
needs a manual bump. Screenshots come from `docs/shots/v4c/`.
