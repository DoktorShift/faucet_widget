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
 * Submit a solved claim.
 *
 * @param {object} args
 * @param {string} args.token     - challenge token from fetchChallenge()
 * @param {string} args.solution  - PoW solution string
 * @param {string} [args.hp]      - honeypot value (always empty for humans)
 */
export async function submitClaim({ token, solution, hp }) {
  const resp = await fetch(`${BASE}/api/claim`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ token, solution, hp: hp ?? '' }),
  })
  return jsonOrThrow(resp)
}

/**
 * Solve a pre-fetched challenge and submit it.
 *
 * The challenge MUST have been fetched at page load (not on submit) so the
 * server's time-on-page check sees a realistic elapsed time. Callers are
 * also responsible for refreshing the challenge when it is close to its
 * server-side expiry.
 *
 * @param {object} args
 * @param {object} args.challenge        - the object returned by fetchChallenge()
 * @param {(p:number)=>void} [args.onProgress] - 0..1 PoW progress callback
 * @param {string} [args.hp]             - honeypot value
 */
export async function runFullClaim({ challenge, onProgress, hp }) {
  const solution = await solvePow(challenge.token, challenge.difficulty, onProgress)
  return submitClaim({ token: challenge.token, solution, hp })
}
