/*
 * Tiny fetch wrapper for the value4value backend.
 *
 * Centralised so we have a single place to:
 * - swap base URL (dev proxy vs prod absolute)
 * - parse JSON errors consistently
 * - surface friendly error keys to the UI layer
 */

import { solvePow } from './usePow.js'

// When served by the FastAPI app itself (production), API is same-origin.
// During `npm run dev`, Vite proxies /api/* to localhost:8000 (vite.config.js).
const BASE = ''

async function jsonOrThrow(resp) {
  let body = null
  try {
    body = await resp.json()
  } catch {
    /* empty body or non-JSON */
  }
  if (!resp.ok) {
    const detail = body?.detail || resp.statusText || 'request failed'
    const err = new Error(detail)
    err.status = resp.status
    err.detail = detail
    throw err
  }
  return body
}

export async function fetchConfig() {
  const resp = await fetch(`${BASE}/api/config`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  })
  return jsonOrThrow(resp)
}

export async function fetchChallenge() {
  const resp = await fetch(`${BASE}/api/challenge`, {
    method: 'GET',
    headers: { Accept: 'application/json' },
  })
  return jsonOrThrow(resp)
}

/**
 * Full claim flow.
 *
 * @param {object} args
 * @param {string} args.token        - challenge token
 * @param {string} args.solution     - PoW solution
 * @param {number} args.startedAt    - seconds unix-ts when page rendered
 * @param {string} args.hp           - honeypot (always empty for humans)
 */
export async function submitClaim({ token, solution, startedAt, hp }) {
  const resp = await fetch(`${BASE}/api/claim`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ token, solution, started_at: startedAt, hp: hp ?? '' }),
  })
  return jsonOrThrow(resp)
}

/**
 * One-shot helper: gets challenge, solves PoW, submits claim. Returns the
 * claim response.
 *
 * @param {(p:number)=>void} onProgress - 0..1 PoW progress
 * @param {number} startedAt - seconds unix-ts; pass the value captured at page load
 * @param {string} hp - honeypot value (the bound input)
 */
export async function runFullClaim({ onProgress, startedAt, hp }) {
  const ch = await fetchChallenge()
  const solution = await solvePow(ch.token, ch.difficulty, onProgress)
  return submitClaim({
    token: ch.token,
    solution,
    startedAt,
    hp,
  })
}
