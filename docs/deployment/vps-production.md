# PurgeDoc VPS production

PurgeDoc runs as the single non-root
`anclora/purgedoc-api:<main-sha>` container on loopback port 8103, exposed only
through `https://api.purgedoc.anclora.com`.

Documents, OCR text, matches, SSE state and active sessions remain ephemeral in
`/tmp/anclora-purgedoc` backed by tmpfs. Neon stores sanitized metadata and audit
records only. Runtime configuration is outside the repository at
`/home/toni/.config/anclora/runtime/purgedoc.env`.
