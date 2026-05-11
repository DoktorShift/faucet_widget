<script setup>
import { ref, computed } from 'vue'
import { runFullClaim } from '@/composables/useApi.js'
import { useI18n } from '@/i18n.js'

const props = defineProps({
  amount: { type: Number, required: true },
})

const { t, lang } = useI18n()

const STATES = Object.freeze({
  IDLE: 'idle',
  WORKING: 'working',
  DONE: 'done',
  ERROR: 'error',
})

const state = ref(STATES.IDLE)
const progress = ref(0)
const claim = ref(null)   // { lnurl, lightning_uri, qr_svg, amount_sats }
const errorKey = ref(null)
const copied = ref(false)
const honeypot = ref('')

// Captured once at component mount — the verifier compares this to the
// server clock at submit time.
const startedAt = Math.floor(Date.now() / 1000)

const ctaLabel = computed(() => {
  if (state.value === STATES.WORKING) {
    return progress.value > 0
      ? t('step2.solving', { progress: Math.round(progress.value * 100) })
      : t('step2.working')
  }
  return t('step2.cta', { amount: props.amount })
})

function errorKeyFromError(err) {
  const detail = (err.detail || err.message || '').toString()
  const status = err.status

  // Network-level failure: fetch threw before getting a response.
  if (!status) return 'error.network'

  if (status === 429) {
    if (/daily|pot/i.test(detail)) return 'error.daily_cap'
    return 'error.ratelimit'
  }
  if (status === 503) return 'error.lnbits'
  if (/expired/i.test(detail)) return 'error.expired'
  if (/slow|wait/i.test(detail)) return 'error.too_fast'
  return 'error.generic'
}

async function onClaim() {
  if (state.value === STATES.WORKING) return
  state.value = STATES.WORKING
  progress.value = 0
  errorKey.value = null

  try {
    const result = await runFullClaim({
      onProgress: (p) => (progress.value = p),
      startedAt,
      hp: honeypot.value,
    })
    claim.value = result
    state.value = STATES.DONE
  } catch (e) {
    errorKey.value = errorKeyFromError(e)
    state.value = STATES.ERROR
  }
}

const copyFailed = ref(false)

async function copyLnurl() {
  if (!claim.value?.lnurl) return
  try {
    await navigator.clipboard.writeText(claim.value.lnurl)
    copied.value = true
    copyFailed.value = false
    setTimeout(() => (copied.value = false), 1500)
  } catch {
    // Clipboard API blocked (insecure context / permissions). Tell the user
    // they can long-press the code instead — don't fail silently.
    copyFailed.value = true
    setTimeout(() => (copyFailed.value = false), 3000)
  }
}

function reset() {
  state.value = STATES.IDLE
  claim.value = null
  errorKey.value = null
  progress.value = 0
}
</script>

<template>
  <div>
    <!-- Idle / working / error: show the CTA -->
    <div v-if="state !== STATES.DONE" class="space-y-4">
      <!-- Honeypot: invisible but present in the DOM. Real users never touch it. -->
      <label class="v4v-hp" aria-hidden="true">
        Website
        <input
          v-model="honeypot"
          type="text"
          name="website"
          tabindex="-1"
          autocomplete="off"
        />
      </label>

      <button
        type="button"
        class="v4v-btn-primary w-full text-base sm:text-lg px-4 sm:px-6 py-4"
        :disabled="state === STATES.WORKING"
        @click="onClaim"
      >
        <svg viewBox="0 0 24 24" class="size-5" fill="currentColor" aria-hidden="true">
          <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" />
        </svg>
        <span>{{ ctaLabel }}</span>
      </button>

      <p v-if="state === STATES.ERROR" class="text-sm text-accent text-center">
        {{ t(errorKey || 'error.generic') }}
      </p>
    </div>

    <!-- Done: show QR + actions -->
    <div v-else class="space-y-4">
      <div class="text-center">
        <p class="v4v-eyebrow mb-2">{{ lang === 'de' ? 'Fertig' : 'Done' }}</p>
        <h3 class="v4v-headline text-2xl sm:text-3xl !leading-tight">{{ t('claim.title') }}</h3>
        <hr class="divider mt-3 mb-4" />
        <p class="text-ink-soft text-sm">{{ t('claim.sub') }}</p>
      </div>

      <div class="v4v-qr max-w-xs mx-auto" v-html="claim.qr_svg" />

      <div class="grid gap-2 sm:grid-cols-2">
        <a
          :href="claim.lightning_uri"
          class="v4v-btn-primary"
        >
          <svg viewBox="0 0 24 24" class="size-5" fill="currentColor" aria-hidden="true">
            <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" />
          </svg>
          {{ t('claim.open_in_wallet') }}
        </a>
        <button type="button" class="v4v-btn-ghost" @click="copyLnurl">
          {{ copied ? t('claim.copied') : t('claim.copy_lnurl') }}
        </button>
      </div>

      <p v-if="copyFailed" class="text-xs text-accent text-center -mt-2">
        {{ t('error.copy_failed') }}
      </p>

      <button type="button" class="text-xs text-ink-mute hover:text-accent block mx-auto" @click="reset">
        {{ t('claim.again') }}
      </button>
    </div>
  </div>
</template>
