// Minimal i18n. Two languages, flat keys, hot-swappable via the lang switcher.
// Defaults to whatever the backend's /api/config says, falls back to "de".

import { ref, computed } from 'vue'

// Voice & tone guidelines for error/status copy:
// - Always explain what to DO next (refresh, wait, come back tomorrow).
// - Never use "Challenge", "Backend", "PoW", "Endpoint", "API", "Token".
// - Friendly but not chirpy. No "Oops!" or excessive exclamation marks.
// - Same key set in embed.js — keep them in sync.
const STRINGS = {
  de: {
    'meta.title': 'value4value · {amount} sats für dich',
    'meta.tagline': 'Du hast einen 21-Bitcoin-Schein gefunden. Empfange jetzt deine ersten Satoshis.',

    'hero.eyebrow': 'Glückwunsch',
    'hero.title': 'Du hast {amount} sats',
    'hero.sub': 'Du hast eine 21-Bitcoin-Note entdeckt. Hier bekommst du deinen allerersten Bitcoin-Bruchteil. Geschenkt, ohne Konto, ohne Tracking.',

    'feature.welldone.title': 'GUT GEMACHT',
    'feature.welldone.body': 'Du hast eine 21-Bitcoin-Note entdeckt und den QR-Code gescannt. Ein vielversprechender Einstieg ins Lernen über das beste Geld der Welt.',
    'feature.gift.title': 'DEIN GESCHENK',
    'feature.gift.body': 'Mit diesem Geschenk überträgst du sicher deine vielleicht ersten Satoshis – die kleinste Einheit von Bitcoin – auf deine eigene Wallet.',
    'feature.experience.title': 'ERFAHRUNG',
    'feature.experience.body': 'Diese Erfahrung ist komplett kostenlos, unverbindlich und risikofrei. Mein Ziel: Dir Bitcoin näherbringen und dir deine ersten Sats schenken.',

    'step1.eyebrow': 'Schritt 1',
    'step1.title': 'Du brauchst eine Lightning-Wallet',
    'step1.sub': 'Eine Lightning-Wallet ist eine App auf deinem Smartphone, in der du Bitcoin sicher empfangen kannst. Hier ein paar Empfehlungen:',
    'step1.skip': 'Ich habe schon eine Wallet',

    'step2.eyebrow': 'Schritt 2',
    'step2.title': 'Deine Sats abholen',
    'step2.sub': 'Tipp auf den Button und ein QR-Code erscheint. Scanne ihn mit deiner Wallet, und schon sind die Sats da.',
    'step2.cta': 'Hol dir {amount} sats',
    'step2.working': 'Einen Moment…',
    'step2.solving': 'Einen Moment… {progress}%',

    'claim.title': 'Scanne mit deiner Wallet',
    'claim.sub': 'Öffne deine Lightning-Wallet, tippe auf „Empfangen" oder „Scannen" und richte die Kamera auf den Code.',
    'claim.open_in_wallet': 'Wallet öffnen',
    'claim.copy_lnurl': 'Code kopieren',
    'claim.copied': 'Kopiert ✓',
    'claim.again': 'Neuen Code holen',

    // All errors are written so a complete beginner knows what to do next.
    'error.expired': 'Das hat zu lange gedauert. Tipp einfach nochmal auf den Button.',
    'error.too_fast': 'Einen kurzen Moment Geduld – dein Code kommt gleich.',
    'error.ratelimit': 'Du hast deine 21 sats schon abgeholt. Für mehr musst du dir einen neuen 21-Bitcoin-Schein suchen ;)',
    'error.daily_cap': 'Heute ist der Topf leer – schon viele Leute haben mitgemacht. Komm morgen wieder!',
    'error.lnbits': 'Das Lightning-Netzwerk ist gerade nicht erreichbar. Versuch es bitte in einer Minute nochmal.',
    'error.network': 'Da ist keine Verbindung. Prüfe dein Internet und versuch es erneut.',
    'error.generic': 'Da ist etwas schiefgegangen. Tipp nochmal auf den Button – meist klappt es dann.',
    'error.page_load': 'Diese Seite konnte nicht geladen werden. Lade sie bitte neu, oder schau in ein paar Minuten wieder vorbei.',
    'error.copy_failed': 'Kopieren hat nicht geklappt. Du kannst den Code aber mit langem Tippen markieren.',

    'footer.disclaimer': 'Selbstverständlich kein echtes Zahlungsmittel. Die 21-Bitcoin-Note dient ausschließlich dem „Orange-Pillen" – also dem aufklärenden Gespräch über Bitcoin. Jedes Detail, vor allem die große 21, ist bewusst so gestaltet, dass auch Laien sofort erkennen: hier liegt kein Geldschein vor.',
    'footer.poweredby': 'Powered by',
    'footer.source': 'Open Source',
  },
  en: {
    'meta.title': 'value4value · {amount} sats for you',
    'meta.tagline': 'You found a 21-bitcoin note. Claim your first satoshis now.',

    'hero.eyebrow': 'Congratulations',
    'hero.title': 'You have {amount} sats',
    'hero.sub': 'You discovered a 21-bitcoin note. Here you get your very first fraction of Bitcoin. A gift, no account, no tracking.',

    'feature.welldone.title': 'WELL DONE',
    'feature.welldone.body': "You discovered a 21-bitcoin note and scanned the QR code – a promising start to learning more about the best money in the world.",
    'feature.gift.title': 'YOUR GIFT',
    'feature.gift.body': 'This gift lets you safely receive your perhaps very first satoshis – the smallest unit of Bitcoin – directly to your own wallet.',
    'feature.experience.title': 'EXPERIENCE',
    'feature.experience.body': 'This experience is completely free, non-binding and risk-free. My goal: get you into Bitcoin and gift you your first sats.',

    'step1.eyebrow': 'Step 1',
    'step1.title': 'You need a Lightning wallet',
    'step1.sub': 'A Lightning wallet is an app on your phone where you can safely receive Bitcoin. Some recommendations:',
    'step1.skip': 'I already have a wallet',

    'step2.eyebrow': 'Step 2',
    'step2.title': 'Claim your sats',
    'step2.sub': "Tap the button and a QR code appears. Scan it with your wallet, and the sats are yours.",
    'step2.cta': 'Get {amount} sats',
    'step2.working': 'One moment…',
    'step2.solving': 'One moment… {progress}%',

    'claim.title': 'Scan with your wallet',
    'claim.sub': 'Open your Lightning wallet, tap "Receive" or "Scan", and point the camera at the code.',
    'claim.open_in_wallet': 'Open wallet',
    'claim.copy_lnurl': 'Copy code',
    'claim.copied': 'Copied ✓',
    'claim.again': 'Get another code',

    'error.expired': 'That took a bit too long. Just tap the button again.',
    'error.too_fast': "One moment please – your code is on the way.",
    'error.ratelimit': "You've already got your 21 sats. For more, you'll need to find another 21-bitcoin note ;)",
    'error.daily_cap': "Today's pot is empty – lots of people joined in. Come back tomorrow!",
    'error.lnbits': 'The Lightning network is unreachable right now. Please try again in a minute.',
    'error.network': "No connection. Check your internet and try again.",
    'error.generic': "Something went wrong. Tap the button again – it usually works on the next try.",
    'error.page_load': "This page couldn't load. Please refresh, or check back in a few minutes.",
    'error.copy_failed': "Couldn't copy automatically. You can long-press the code to select it.",

    'footer.disclaimer': "Of course not a real means of payment. The 21-bitcoin note exists purely to 'orangepill' the conversation about Bitcoin. Every detail – especially the large 21 – has been changed clearly enough that anyone can see at a glance: this is not a banknote.",
    'footer.poweredby': 'Powered by',
    'footer.source': 'Open Source',
  },
}

export const SUPPORTED_LANGS = ['de', 'en']

export const lang = ref('de')

export function setLang(next) {
  if (SUPPORTED_LANGS.includes(next)) {
    lang.value = next
    try {
      document.documentElement.lang = next
      localStorage.setItem('v4v.lang', next)
    } catch {
      /* ignore — non-critical */
    }
  }
}

// Restore preference on load.
// Priority: ?lang= query string  →  localStorage  →  backend default.
try {
  const params = new URLSearchParams(window.location.search)
  const fromQuery = params.get('lang')
  if (fromQuery && SUPPORTED_LANGS.includes(fromQuery)) {
    lang.value = fromQuery
  } else {
    const saved = localStorage.getItem('v4v.lang')
    if (saved && SUPPORTED_LANGS.includes(saved)) lang.value = saved
  }
} catch {
  /* ignore */
}

function interpolate(template, vars) {
  return template.replace(/\{(\w+)\}/g, (_m, k) => (k in vars ? String(vars[k]) : `{${k}}`))
}

export function t(key, vars = {}) {
  const dict = STRINGS[lang.value] || STRINGS.de
  const tpl = dict[key] ?? STRINGS.de[key] ?? key
  return interpolate(tpl, vars)
}

export function useI18n() {
  return {
    t: (key, vars) => t(key, vars),
    lang: computed(() => lang.value),
    setLang,
  }
}
