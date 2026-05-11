/*
 * Proof-of-work solver, used both by the landing page and the embed.
 *
 * Given a token + difficulty (leading zero bits required), find a `solution`
 * such that SHA-256(token + ':' + solution) starts with `difficulty` zero bits.
 *
 * Runs cooperatively: yields to the event loop every CHUNK iterations so the
 * UI stays responsive. Reports progress so we can show a spinner percentage.
 *
 * No worker — keeps things dependency-free and avoids the cross-origin script
 * complexity inside the embed widget. For difficulty 16–20 this completes in
 * well under a second on modern hardware, which is what we tune for.
 */

const CHUNK = 2000
const MAX_ATTEMPTS = 10_000_000   // safety cap, prevents runaway in pathological cases

const enc = new TextEncoder()

async function sha256(bytes) {
  const buf = await crypto.subtle.digest('SHA-256', bytes)
  return new Uint8Array(buf)
}

function leadingZeroBits(bytes) {
  let count = 0
  for (let i = 0; i < bytes.length; i++) {
    const b = bytes[i]
    if (b === 0) {
      count += 8
      continue
    }
    for (let mask = 0x80; mask; mask >>= 1) {
      if (b & mask) return count
      count += 1
    }
    return count
  }
  return count
}

/**
 * Solve a PoW challenge.
 *
 * @param {string} token   - The opaque challenge from /api/challenge
 * @param {number} difficulty - Required leading zero bits
 * @param {(p: number) => void} [onProgress] - Called with 0..1 progress fraction
 * @returns {Promise<string>} The solution string
 */
export async function solvePow(token, difficulty, onProgress) {
  let attempt = 0
  // Approximate expected attempts: 2^difficulty. Use it to drive a smooth
  // progress bar even though probabilistically we could solve faster or slower.
  const expected = Math.pow(2, difficulty)

  while (attempt < MAX_ATTEMPTS) {
    for (let i = 0; i < CHUNK; i++) {
      const solution = attempt.toString(36)
      const digest = await sha256(enc.encode(`${token}:${solution}`))
      if (leadingZeroBits(digest) >= difficulty) {
        if (onProgress) onProgress(1)
        return solution
      }
      attempt += 1
    }
    if (onProgress) {
      onProgress(Math.min(0.99, attempt / expected))
    }
    // Yield to the event loop so the UI stays interactive.
    await new Promise((r) => setTimeout(r, 0))
  }
  throw new Error('PoW solver gave up — difficulty too high or environment too slow.')
}
