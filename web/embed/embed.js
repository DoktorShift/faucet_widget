/*
 * value4value embed widget
 * ────────────────────────────────────────────────────────────────────────────
 * Drop into any 3rd-party page:
 *
 *   <script src="https://value4value.eu/embed.js" defer></script>
 *   <button data-v4v-claim>⚡ Get 21 sats</button>
 *
 * The script auto-attaches to every element with `data-v4v-claim`. On click it
 * opens a modal (rendered in a Shadow DOM, so the host page's CSS can't break
 * it and vice versa), runs the same claim flow as the standalone landing,
 * and displays the resulting QR / LNURL.
 *
 * Configuration via `data-` attributes on the script tag:
 *   data-v4v-origin="https://value4value.eu"   (where the API lives)
 *   data-v4v-lang="de" | "en"                  (override UI language)
 *
 * Build target: ES2018, IIFE, minified. No framework, no runtime deps.
 */

;(() => {
  // Don't initialise twice if loaded by accident
  if (window.__V4V_EMBED__) return
  window.__V4V_EMBED__ = true

  const SCRIPT = document.currentScript
  const ORIGIN = (SCRIPT && SCRIPT.dataset.v4vOrigin) || _inferOrigin()
  const FORCED_LANG = SCRIPT && SCRIPT.dataset.v4vLang

  // ── i18n (subset of the landing-page strings — keep in sync with i18n.js) ─
  // Voice rules: no "Challenge"/"Backend"/"PoW"/"API". Friendly, actionable.
  const STRINGS = {
    de: {
      title: '{amount} sats für dich',
      sub: 'Scanne den QR-Code mit deiner Lightning-Wallet.',
      cta: 'Hol dir {amount} sats',
      working: 'Einen Moment…',
      solving: 'Einen Moment… {progress}%',
      open: 'Wallet öffnen',
      copy: 'Code kopieren',
      copied: 'Kopiert ✓',
      again: 'Neuen Code holen',
      close: 'Schließen',
      err_expired: 'Das hat zu lange gedauert. Tipp einfach nochmal auf den Button.',
      err_too_fast: 'Einen kurzen Moment Geduld – dein Code kommt gleich.',
      err_ratelimit: 'Du hast deine 21 sats schon abgeholt. Für mehr musst du dir einen neuen 21-Bitcoin-Schein suchen ;)',
      err_daily_cap: 'Heute ist der Topf leer. Komm morgen wieder!',
      err_lnbits: 'Das Lightning-Netzwerk ist gerade nicht erreichbar. Versuch es bitte in einer Minute nochmal.',
      err_network: 'Da ist keine Verbindung. Prüfe dein Internet und versuch es erneut.',
      err_generic: 'Da ist etwas schiefgegangen. Tipp nochmal auf den Button.',
      err_copy: 'Kopieren ging nicht. Du kannst den Code mit langem Tippen markieren.',
    },
    en: {
      title: '{amount} sats for you',
      sub: 'Scan the QR code with your Lightning wallet.',
      cta: 'Get {amount} sats',
      working: 'One moment…',
      solving: 'One moment… {progress}%',
      open: 'Open wallet',
      copy: 'Copy code',
      copied: 'Copied ✓',
      again: 'Get another code',
      close: 'Close',
      err_expired: 'That took a bit too long. Just tap the button again.',
      err_too_fast: 'One moment please – your code is on the way.',
      err_ratelimit: "You've already got your 21 sats. For more, you'll need to find another 21-bitcoin note ;)",
      err_daily_cap: "Today's pot is empty. Come back tomorrow!",
      err_lnbits: 'The Lightning network is unreachable right now. Please try again in a minute.',
      err_network: 'No connection. Check your internet and try again.',
      err_generic: "Something went wrong. Tap the button again.",
      err_copy: "Couldn't copy. You can long-press the code to select it.",
    },
  }

  function t(lang, key, vars) {
    const dict = STRINGS[lang] || STRINGS.de
    const tpl = dict[key] || STRINGS.de[key] || key
    return tpl.replace(/\{(\w+)\}/g, (_m, k) => (vars && k in vars ? vars[k] : `{${k}}`))
  }

  // ── PoW solver (mirrors composables/usePow.js) ───────────────────────────
  const enc = new TextEncoder()

  function leadingZeroBits(u8) {
    let count = 0
    for (let i = 0; i < u8.length; i++) {
      const b = u8[i]
      if (b === 0) {
        count += 8
        continue
      }
      for (let m = 0x80; m; m >>= 1) {
        if (b & m) return count
        count += 1
      }
      return count
    }
    return count
  }

  async function solvePow(token, difficulty, onProgress) {
    const CHUNK = 2000
    const MAX = 10_000_000
    const expected = Math.pow(2, difficulty)
    let attempt = 0
    while (attempt < MAX) {
      for (let i = 0; i < CHUNK; i++) {
        const sol = attempt.toString(36)
        const buf = await crypto.subtle.digest('SHA-256', enc.encode(`${token}:${sol}`))
        if (leadingZeroBits(new Uint8Array(buf)) >= difficulty) {
          onProgress && onProgress(1)
          return sol
        }
        attempt += 1
      }
      onProgress && onProgress(Math.min(0.99, attempt / expected))
      await new Promise((r) => setTimeout(r, 0))
    }
    throw new Error('pow_gaveup')
  }

  // ── API ──────────────────────────────────────────────────────────────────
  async function api(path, opts) {
    const resp = await fetch(`${ORIGIN}${path}`, opts)
    let body = null
    try {
      body = await resp.json()
    } catch {
      /* */
    }
    if (!resp.ok) {
      const err = new Error(body?.detail || resp.statusText || 'request_failed')
      err.status = resp.status
      err.detail = body?.detail
      throw err
    }
    return body
  }

  const fetchConfig = () => api('/api/config', { headers: { Accept: 'application/json' } })
  const fetchChallenge = () => api('/api/challenge', { headers: { Accept: 'application/json' } })
  const submitClaim = (payload) =>
    api('/api/claim', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify(payload),
    })

  // ── styles (scoped to shadow root) ───────────────────────────────────────
  const CSS = `
  :host { all: initial; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
  * { box-sizing: border-box; }

  .backdrop {
    position: fixed; inset: 0;
    background: rgba(15, 15, 15, 0.78);
    backdrop-filter: blur(4px);
    z-index: 2147483646;
    display: flex; align-items: center; justify-content: center;
    padding: 1rem;
    opacity: 0; transition: opacity 180ms ease-out;
  }
  .backdrop.in { opacity: 1; }

  .modal {
    background: #1f1f1f;
    color: #fff;
    border-radius: 14px;
    width: 100%; max-width: 420px;
    padding: 1.75rem 1.5rem 1.5rem;
    box-shadow: 0 0 0 1px rgba(247,147,26,.25), 0 20px 60px -10px rgba(0,0,0,.5);
    position: relative;
    transform: translateY(8px) scale(.98);
    transition: transform 200ms ease-out;
  }
  .backdrop.in .modal { transform: translateY(0) scale(1); }

  .close {
    position: absolute; top: .75rem; right: .75rem;
    background: transparent; border: 0; cursor: pointer;
    color: #9a9a9a; font-size: 1.5rem; line-height: 1;
    padding: .25rem .5rem; border-radius: 6px;
    transition: color 120ms;
  }
  .close:hover { color: #fff; }

  h2 {
    color: #f7931a;
    font-weight: 300;
    font-size: 1.75rem;
    letter-spacing: 0.06em;
    margin: 0 0 .5rem;
    text-align: center;
  }
  .sub { color: #d0d0d0; text-align: center; margin: 0 0 1.25rem; font-size: .95rem; }

  .btn {
    display: inline-flex; align-items: center; justify-content: center; gap: .5rem;
    border-radius: 10px; padding: .75rem 1.25rem;
    font-weight: 500; letter-spacing: .03em; font-size: 1rem;
    cursor: pointer; border: 0;
    transition: all 150ms;
    width: 100%;
  }
  .btn:disabled { opacity: .45; cursor: not-allowed; }
  .btn-primary {
    background: #f7931a; color: #1f1f1f;
    box-shadow: 0 0 0 1px rgba(247,147,26,.3), 0 8px 24px -8px rgba(247,147,26,.4);
  }
  .btn-primary:hover:not(:disabled) { background: #ffa940; }
  .btn-ghost {
    background: transparent; color: #d0d0d0;
    box-shadow: inset 0 0 0 1px #3a3a3a;
  }
  .btn-ghost:hover { color: #fff; box-shadow: inset 0 0 0 1px rgba(247,147,26,.5); }

  .row { display: grid; grid-template-columns: 1fr 1fr; gap: .5rem; margin-top: 1rem; }
  @media (max-width: 380px) { .row { grid-template-columns: 1fr; } }

  .err { color: #f7931a; text-align: center; font-size: .85rem; margin-top: .75rem; }

  .qr {
    width: 100%; max-width: 280px; margin: 1rem auto;
    background: #fff; border-radius: 10px; padding: 12px;
  }
  .qr svg { width: 100%; height: auto; display: block; }

  .again {
    display: block; margin: .75rem auto 0; background: transparent;
    border: 0; color: #9a9a9a; cursor: pointer; font-size: .8rem;
    padding: .25rem .5rem;
  }
  .again:hover { color: #f7931a; }

  /* honeypot */
  .hp { position: absolute !important; left: -10000px; top: auto;
        width: 1px; height: 1px; overflow: hidden; opacity: 0; }
  `

  // ── DOM helpers ──────────────────────────────────────────────────────────
  function el(tag, attrs, ...children) {
    const e = document.createElement(tag)
    if (attrs) {
      for (const k in attrs) {
        if (k === 'class') e.className = attrs[k]
        else if (k.startsWith('on') && typeof attrs[k] === 'function') {
          e.addEventListener(k.slice(2), attrs[k])
        } else if (k === 'html') {
          e.innerHTML = attrs[k]
        } else {
          e.setAttribute(k, attrs[k])
        }
      }
    }
    for (const c of children.flat()) {
      if (c == null || c === false) continue
      e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c)
    }
    return e
  }

  function errorKey(status, detail) {
    // No status code = the fetch never completed → network/CORS/offline
    if (!status) return 'err_network'
    const d = (detail || '').toLowerCase()
    if (status === 429) return /daily|pot/.test(d) ? 'err_daily_cap' : 'err_ratelimit'
    if (status === 503) return 'err_lnbits'
    if (/expired/.test(d)) return 'err_expired'
    if (/slow|wait/.test(d)) return 'err_too_fast'
    return 'err_generic'
  }

  function _inferOrigin() {
    if (SCRIPT && SCRIPT.src) {
      try {
        return new URL(SCRIPT.src).origin
      } catch {
        /* fall through */
      }
    }
    return ''
  }

  // ── modal renderer ───────────────────────────────────────────────────────
  let host = null
  let shadow = null

  function ensureHost() {
    if (host) return host
    host = document.createElement('div')
    host.style.all = 'initial'
    document.body.appendChild(host)
    shadow = host.attachShadow({ mode: 'closed' })
    const style = document.createElement('style')
    style.textContent = CSS
    shadow.appendChild(style)
    return host
  }

  function close() {
    if (!host) return
    const bd = shadow.querySelector('.backdrop')
    if (bd) bd.classList.remove('in')
    setTimeout(() => {
      if (host && host.parentNode) host.parentNode.removeChild(host)
      host = null
      shadow = null
    }, 200)
  }

  async function openModal() {
    ensureHost()

    let cfg
    try {
      cfg = await fetchConfig()
    } catch {
      // Render a minimal error
      const bd = el('div', { class: 'backdrop' },
        el('div', { class: 'modal' },
          el('h2', null, '⚠️'),
          el('p', { class: 'err' }, t('en', 'err_generic')),
          el('button', { class: 'btn btn-ghost', onclick: close }, t('en', 'close')),
        ),
      )
      shadow.appendChild(bd)
      requestAnimationFrame(() => bd.classList.add('in'))
      return
    }

    const lang = FORCED_LANG || cfg.default_lang || 'de'
    const amount = cfg.amount_sats

    const startedAt = Math.floor(Date.now() / 1000)
    let copied = false
    let claim = null

    // Build DOM
    const body = el('div', { class: 'body' })
    const errLine = el('p', { class: 'err', style: 'display:none' })
    const honeypot = el('input', { type: 'text', tabindex: '-1', autocomplete: 'off', name: 'website' })
    const hpWrap = el('label', { class: 'hp', 'aria-hidden': 'true' }, 'Website', honeypot)

    const cta = el('button', { class: 'btn btn-primary' }, `⚡ ${t(lang, 'cta', { amount })}`)

    function showError(key) {
      errLine.textContent = t(lang, key)
      errLine.style.display = ''
    }

    cta.onclick = async () => {
      cta.disabled = true
      errLine.style.display = 'none'
      cta.textContent = `⚡ ${t(lang, 'working')}`

      try {
        const ch = await fetchChallenge()
        const solution = await solvePow(ch.token, ch.difficulty, (p) => {
          cta.textContent = `⚡ ${t(lang, 'solving', { progress: Math.round(p * 100) })}`
        })
        claim = await submitClaim({
          token: ch.token,
          solution,
          started_at: startedAt,
          hp: honeypot.value,
        })
        renderDone()
      } catch (e) {
        showError(errorKey(e.status, e.detail || e.message))
        cta.disabled = false
        cta.textContent = `⚡ ${t(lang, 'cta', { amount })}`
      }
    }

    function renderIdle() {
      body.innerHTML = ''
      // Reset CTA visual state — it may have stale "solving 100%" text from a
      // previous run when the user clicks "again".
      cta.disabled = false
      cta.textContent = `⚡ ${t(lang, 'cta', { amount })}`
      errLine.style.display = 'none'

      body.appendChild(el('h2', null, t(lang, 'title', { amount })))
      body.appendChild(el('p', { class: 'sub' }, t(lang, 'sub')))
      body.appendChild(hpWrap)
      body.appendChild(cta)
      body.appendChild(errLine)
    }

    function renderDone() {
      body.innerHTML = ''
      body.appendChild(el('h2', null, t(lang, 'title', { amount })))
      body.appendChild(el('p', { class: 'sub' }, t(lang, 'sub')))
      body.appendChild(el('div', { class: 'qr', html: claim.qr_svg }))

      const openBtn = el('a', { class: 'btn btn-primary', href: claim.lightning_uri }, '⚡', t(lang, 'open'))
      const copyBtn = el('button', { class: 'btn btn-ghost' }, t(lang, 'copy'))
      // Inline status line for copy-fail messages — local to renderDone so
      // it survives navigation between idle/done states.
      const copyStatus = el('p', { class: 'err', style: 'display:none' })
      copyBtn.onclick = async () => {
        try {
          await navigator.clipboard.writeText(claim.lnurl)
          copied = true
          copyBtn.textContent = t(lang, 'copied')
          copyStatus.style.display = 'none'
          setTimeout(() => {
            copied = false
            copyBtn.textContent = t(lang, 'copy')
          }, 1500)
        } catch {
          copyStatus.textContent = t(lang, 'err_copy')
          copyStatus.style.display = ''
        }
      }
      const row = el('div', { class: 'row' }, openBtn, copyBtn)
      body.appendChild(row)
      body.appendChild(copyStatus)

      const again = el('button', { class: 'again' }, t(lang, 'again'))
      again.onclick = () => { claim = null; cta.disabled = false; renderIdle() }
      body.appendChild(again)
    }

    renderIdle()

    const closeBtn = el('button', { class: 'close', 'aria-label': t(lang, 'close'), onclick: close }, '×')
    const modal = el('div', { class: 'modal' }, closeBtn, body)
    const backdrop = el('div', { class: 'backdrop', onclick: (e) => { if (e.target === backdrop) close() } }, modal)
    shadow.appendChild(backdrop)
    requestAnimationFrame(() => backdrop.classList.add('in'))

    // ESC to close
    function onKey(e) {
      if (e.key === 'Escape') { close(); document.removeEventListener('keydown', onKey) }
    }
    document.addEventListener('keydown', onKey)
  }

  // ── auto-attach to data-v4v-claim buttons OR .v4v-claim class ────────────
  // Class-based fallback handles cases where heavy-handed WP sanitisers strip
  // `data-*` attributes from posts. The class survives wp_kses.
  const SELECTOR = '[data-v4v-claim], .v4v-claim'

  function bind(root) {
    if (!root.querySelectorAll) return
    root.querySelectorAll(SELECTOR).forEach((btn) => {
      if (btn.__v4vBound) return
      btn.__v4vBound = true
      btn.addEventListener('click', (e) => {
        e.preventDefault()
        openModal()
      })
    })
  }

  // Observe DOM in case the host page injects buttons dynamically
  function start() {
    bind(document)
    if (typeof MutationObserver !== 'undefined') {
      new MutationObserver((muts) => {
        for (const m of muts) {
          for (const n of m.addedNodes) {
            if (n.nodeType === 1) bind(n)
          }
        }
      }).observe(document.documentElement, { childList: true, subtree: true })
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start)
  } else {
    start()
  }

  // Expose a tiny manual API for advanced cases
  window.V4V = { open: openModal, close }
})()
