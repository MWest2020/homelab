---
title: Cloudflare Pages — a stuck build
sidebar_position: 5
---

# Cloudflare Pages — a stuck build

The Pages projects on the account (`westerweel-work`, `homelab`, production
branch `main`) share one build slot. A build that hangs in *initialize* keeps
every later commit *queued* behind it.

Use a token scoped to Pages only (kept in a 0600 env file, never in git) and
the Pages deployments API:

1. `GET /accounts/{account}/pages/projects/{project}/deployments?per_page=6` —
   the hanger is the deployment in stage `initialize` or `queued` with status
   `active` for more than five minutes.
2. `POST …/deployments/{id}/retry` on it.
3. If the retry is also stuck in *queued*:
   `DELETE …/deployments/{id}?force=true` on the **original** hanger. It holds
   the slot; the queue then builds on.
4. Verify on the live site, for example `article:modified_time` in the page
   head. The PaperMod theme minifies without quotes (`href=https://…`), so do
   not grep for `href="`.
