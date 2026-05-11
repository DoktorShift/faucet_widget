<script setup>
import { h, ref, onMounted, watch } from 'vue'
import { fetchConfig } from '@/composables/useApi.js'
import { setLang, useI18n } from '@/i18n.js'
import WalletList from '@/components/WalletList.vue'
import ClaimFlow from '@/components/ClaimFlow.vue'
import LangSwitch from '@/components/LangSwitch.vue'
import lnbitsLogo from '@/assets/lnbits-full-inverse.svg'
import billBannerDesktop from '@/assets/billart/eurobill_header.jpg'
import billBannerMobile from '@/assets/billart/noten.png'
import billBack from '@/assets/billart/rueckseite_genesis.jpg'

const { t, lang } = useI18n()
const config = ref(null)
const loadError = ref(false)

onMounted(async () => {
  try {
    const cfg = await fetchConfig()
    config.value = cfg
    if (!localStorage.getItem('v4v.lang') && !new URLSearchParams(location.search).get('lang')) {
      setLang(cfg.default_lang)
    }
  } catch {
    loadError.value = true
  }
})

function reloadPage() {
  location.reload()
}

watch([config, lang], () => {
  if (config.value) {
    document.title = t('meta.title', { amount: config.value.amount_sats })
  }
}, { immediate: true })

// ─── inline icons ───────────────────────────────────────────────────────────
const ICON = { viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
  'stroke-width': 1.4, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }

const IconTrophy = { render: () => h('svg', ICON, [
  h('path', { d: 'M8 4h8v5a4 4 0 0 1-8 0V4Z' }),
  h('path', { d: 'M8 6H5v2a3 3 0 0 0 3 3' }),
  h('path', { d: 'M16 6h3v2a3 3 0 0 1-3 3' }),
  h('path', { d: 'M10 14h4v3h-4z' }),
  h('path', { d: 'M7 21h10' }),
  h('path', { d: 'M12 17v4' }),
]) }
const IconGift = { render: () => h('svg', ICON, [
  h('rect', { x: 3, y: 8, width: 18, height: 4, rx: 1 }),
  h('path', { d: 'M5 12v9h14v-9' }),
  h('path', { d: 'M12 8v13' }),
  h('path', { d: 'M12 8S9 3 7 5s.5 3 5 3' }),
  h('path', { d: 'M12 8s3-5 5-3-.5 3-5 3' }),
]) }
const IconBulb = { render: () => h('svg', ICON, [
  h('path', { d: 'M9 18h6' }),
  h('path', { d: 'M10 21h4' }),
  h('path', { d: 'M12 3a6 6 0 0 0-4 10.5c.7.7 1.2 1.5 1.4 2.5h5.2c.2-1 .7-1.8 1.4-2.5A6 6 0 0 0 12 3Z' }),
]) }
const IconHeart = { render: () => h('svg', { ...ICON, 'stroke-width': 1.3 }, [
  h('path', { d: 'M12 21s-7-4.5-9-9.5C2 7 5 4 8 4c2 0 3 1 4 2.5C13 5 14 4 16 4c3 0 6 3 5 7.5C19 16.5 12 21 12 21z' }),
]) }

const features = [
  { key: 'welldone', icon: IconTrophy },
  { key: 'gift', icon: IconGift },
  { key: 'experience', icon: IconBulb },
]
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <!-- Slim header bar — controls sit over the hero banner so we use
         backdrop-blur pills to keep them readable against the image.
         pt with safe-area-inset so the chips clear the iPhone notch. -->
    <header class="absolute top-0 inset-x-0 z-20"
            :style="{ paddingTop: 'env(safe-area-inset-top, 0)' }">
      <div class="max-w-6xl mx-auto px-4 sm:px-6 py-3 sm:py-4
                  flex items-center justify-between">
        <a href="/"
           class="group inline-flex items-center gap-2
                  bg-bg/55 backdrop-blur-md
                  ring-1 ring-white/15
                  shadow-[0_4px_14px_-6px_rgba(0,0,0,0.6)]
                  rounded-full pl-1.5 pr-3
                  min-h-9 py-1">
          <span class="inline-block size-6 rounded-full bg-accent text-bg
                       grid place-items-center text-[0.7rem] font-bold">₿</span>
          <span class="uppercase tracking-headline text-xs sm:text-sm text-ink
                       group-hover:text-accent transition-colors">value4value</span>
        </a>
        <LangSwitch />
      </div>
    </header>

    <!-- Loading -->
    <div v-if="!config && !loadError" class="flex-1 flex items-center justify-center">
      <div class="size-8 rounded-full border-2 border-accent/30 border-t-accent animate-spin" />
    </div>

    <!-- Load failed -->
    <div v-else-if="loadError" class="flex-1 flex items-center justify-center px-4">
      <div class="max-w-md text-center space-y-4">
        <p class="text-ink-soft">{{ t('error.page_load') }}</p>
        <button type="button" class="v4v-btn-ghost" @click="reloadPage">
          {{ lang === 'de' ? 'Seite neu laden' : 'Reload page' }}
        </button>
      </div>
    </div>

    <main v-else class="flex-1">

      <!-- ─── HERO — bills as the first impression, big & dramatic ────── -->
      <!-- Two distinct assets for two viewports:
           · noten.png (horizontal strip, bills side-by-side, ~3.56:1)
             is shown on mobile portrait, where dramatic eurobill would
             crop to the overlap zone and look weird.
           · eurobill_header.jpg (overlapping bills with shadows, ~1.67:1)
             is shown sm and up, where the wider container lets the
             composition breathe. -->
      <section class="relative isolate overflow-hidden">
        <div class="relative h-[54vh] min-h-[340px] max-h-[480px]
                    sm:h-[60vh] sm:min-h-[420px] sm:max-h-[640px]
                    md:h-[64vh] md:max-h-[680px]
                    w-full">
          <picture>
            <source media="(min-width: 640px)" :srcset="billBannerDesktop" />
            <img
              :src="billBannerMobile"
              alt=""
              aria-hidden="true"
              class="w-full h-full object-cover object-center
                     select-none pointer-events-none"
            />
          </picture>
          <!-- Soft bottom fade into page bg so the headline can sit
               immediately under the bills without a hard seam. -->
          <div class="absolute inset-x-0 bottom-0 h-2/5 bg-gradient-to-b from-transparent to-bg" />
          <!-- Top vignette so the header chips have a contrast surface -->
          <div class="absolute inset-x-0 top-0 h-24 bg-gradient-to-b from-bg/60 to-transparent" />
        </div>

        <!-- Hero title — sits just below the banner, fluid size scales
             smoothly from 320 px phones to 4K. -->
        <div class="max-w-3xl mx-auto px-5 sm:px-6 -mt-3 sm:-mt-8 relative z-10 text-center">
          <h1 class="font-light tracking-headline text-accent
                     text-[clamp(2.5rem,9vw,6.5rem)]
                     !leading-[1.02] mb-5 sm:mb-6
                     drop-shadow-[0_2px_22px_rgba(0,0,0,0.7)]">
            {{ lang === 'de' ? 'Glückwunsch!' : 'Congratulations!' }}
          </h1>
          <p class="text-ink-soft text-[0.95rem] sm:text-lg
                    max-w-2xl mx-auto leading-relaxed
                    px-2 sm:px-0">
            {{ t('hero.sub') }}
          </p>

          <!-- Heart disc — signature detail -->
          <div class="mt-8 sm:mt-10 flex justify-center">
            <div class="size-11 rounded-full bg-bg-soft/70 ring-1 ring-line
                        grid place-items-center text-accent">
              <component :is="IconHeart" class="size-5" aria-hidden="true" />
            </div>
          </div>
        </div>
      </section>

      <!-- ─── Three feature columns ──────────────────────────────────── -->
      <section class="max-w-5xl mx-auto px-6 pt-16 sm:pt-20 pb-20 sm:pb-28">
        <div class="grid gap-12 sm:gap-10 sm:grid-cols-3">
          <article
            v-for="f in features"
            :key="f.key"
            class="relative text-center sm:text-left
                   sm:[&:not(:first-child)]:pl-10
                   sm:[&:not(:first-child)]:border-l sm:[&:not(:first-child)]:border-line/40"
          >
            <hr class="sm:hidden border-0 h-px bg-line/60 w-16 mx-auto mb-6" />
            <component :is="f.icon" class="size-9 text-accent mb-5 inline-block sm:block" aria-hidden="true" />
            <h3 class="uppercase tracking-headline text-sm font-semibold text-ink mb-3">
              {{ t(`feature.${f.key}.title`) }}
            </h3>
            <p class="text-ink-soft text-sm leading-relaxed">
              {{ t(`feature.${f.key}.body`) }}
            </p>
          </article>
        </div>
      </section>

      <!-- ─── Disclaimer band — stamp-style notice, full-width orange ─── -->
      <section class="relative bg-accent text-bg overflow-hidden">
        <!-- decorative diagonal hatching, like a security strip on a banknote -->
        <div
          aria-hidden="true"
          class="absolute inset-0 opacity-[0.07] pointer-events-none"
          :style="{
            backgroundImage:
              'repeating-linear-gradient(135deg, #1f1f1f 0 2px, transparent 2px 14px)'
          }"
        />
        <!-- giant outlined warning glyph at left as ambient mark -->
        <svg
          aria-hidden="true"
          viewBox="0 0 24 24" fill="none" stroke="currentColor"
          stroke-width="0.5" stroke-linecap="round" stroke-linejoin="round"
          class="absolute -left-8 sm:-left-4 top-1/2 -translate-y-1/2
                 w-40 sm:w-48 opacity-15 pointer-events-none"
        >
          <path d="M12 3 2 21h20L12 3Z" />
          <path d="M12 10v5" />
          <circle cx="12" cy="18" r=".6" fill="currentColor" />
        </svg>

        <div class="relative max-w-2xl mx-auto px-6 py-12 sm:py-14 text-center">
          <p class="uppercase tracking-headline text-[0.65rem] font-semibold mb-3
                    inline-flex items-center gap-2">
            <span class="size-1.5 rounded-full bg-bg" aria-hidden="true" />
            {{ lang === 'de' ? 'Wichtiger Hinweis' : 'Important Disclaimer' }}
            <span class="size-1.5 rounded-full bg-bg" aria-hidden="true" />
          </p>
          <p class="text-[0.95rem] sm:text-base leading-relaxed font-medium mb-5">
            {{ t('footer.disclaimer') }}
          </p>
          <a
            href="https://21m.art"
            target="_blank"
            rel="noopener"
            class="inline-flex items-center gap-1.5
                   text-xs uppercase tracking-headline font-semibold
                   border-b border-bg/40 hover:border-bg pb-0.5
                   transition-colors"
          >
            {{ lang === 'de' ? 'Mehr zum Projekt' : 'More about the project' }}
            <span aria-hidden="true">→</span>
          </a>
        </div>
      </section>

      <!-- ─── Wallet section — curated, BuhoGO featured ───────────────── -->
      <section class="max-w-4xl mx-auto px-4 sm:px-6 py-20 sm:py-28">
        <header class="mb-12 text-center">
          <h2 class="v4v-headline text-3xl sm:text-4xl !leading-tight">{{ t('step1.title') }}</h2>
          <hr class="divider mt-4 mb-5" />
          <p class="text-ink-soft max-w-xl mx-auto">{{ t('step1.sub') }}</p>
        </header>
        <WalletList :wallets="config.wallets" />
      </section>

      <!-- ─── Claim — focal moment ───────────────────────────────────── -->
      <section class="relative">
        <!-- subtle back-of-bill texture as ambient detail -->
        <div
          aria-hidden="true"
          class="absolute inset-0 opacity-[0.04] bg-cover bg-center pointer-events-none"
          :style="{ backgroundImage: `url(${billBack})` }"
        />
        <div class="relative max-w-xl mx-auto px-4 sm:px-6 py-20 sm:py-28">
          <header class="mb-10 text-center">
            <h2 class="v4v-headline text-3xl sm:text-4xl !leading-tight">{{ t('step2.title') }}</h2>
            <hr class="divider mt-4 mb-5" />
            <p class="text-ink-soft">{{ t('step2.sub') }}</p>
          </header>
          <div class="v4v-card ring-1 ring-line/40 bg-bg-soft">
            <ClaimFlow :amount="config.amount_sats" />
          </div>
        </div>
      </section>
    </main>

    <!-- Footer — three columns of real, useful links -->
    <footer class="border-t border-line/40 bg-bg-deep/50"
            :style="{ paddingBottom: 'env(safe-area-inset-bottom, 0)' }">
      <div class="max-w-5xl mx-auto px-6 py-12 sm:py-14
                  grid gap-10 sm:gap-12 sm:grid-cols-3">

        <!-- Column 1 — Project -->
        <div class="space-y-3">
          <p class="v4v-eyebrow">
            {{ lang === 'de' ? 'Projekt' : 'Project' }}
          </p>
          <ul class="space-y-2 text-sm">
            <li>
              <a href="https://21m.art" target="_blank" rel="noopener"
                 class="text-ink-soft hover:text-accent transition-colors inline-flex items-center gap-1">
                21m.art <span aria-hidden="true" class="text-xs">↗</span>
              </a>
            </li>
            <li>
              <a href="https://21mio.eu" target="_blank" rel="noopener"
                 class="text-ink-soft hover:text-accent transition-colors inline-flex items-center gap-1">
                21mio.eu <span aria-hidden="true" class="text-xs">↗</span>
              </a>
            </li>
            <li>
              <a href="https://21m.art/?page_id=1628#about" target="_blank" rel="noopener"
                 class="text-ink-soft hover:text-accent transition-colors inline-flex items-center gap-1">
                {{ lang === 'de' ? 'Über das Projekt' : 'About the project' }}
                <span aria-hidden="true" class="text-xs">↗</span>
              </a>
            </li>
          </ul>
        </div>

        <!-- Column 2 — Wallets -->
        <div class="space-y-3">
          <p class="v4v-eyebrow">
            {{ lang === 'de' ? 'Wallets' : 'Wallets' }}
          </p>
          <ul class="space-y-2 text-sm">
            <li>
              <a href="https://home.mybuho.de/buhogo" target="_blank" rel="noopener"
                 class="text-ink-soft hover:text-accent transition-colors inline-flex items-center gap-1">
                BuhoGO <span aria-hidden="true" class="text-xs">↗</span>
              </a>
            </li>
            <li>
              <a href="https://blink.sv" target="_blank" rel="noopener"
                 class="text-ink-soft hover:text-accent transition-colors inline-flex items-center gap-1">
                Blink <span aria-hidden="true" class="text-xs">↗</span>
              </a>
            </li>
            <li>
              <a href="https://phoenix.acinq.co" target="_blank" rel="noopener"
                 class="text-ink-soft hover:text-accent transition-colors inline-flex items-center gap-1">
                Phoenix <span aria-hidden="true" class="text-xs">↗</span>
              </a>
            </li>
            <li>
              <a href="https://www.walletofsatoshi.com" target="_blank" rel="noopener"
                 class="text-ink-soft hover:text-accent transition-colors inline-flex items-center gap-1">
                Wallet of Satoshi <span aria-hidden="true" class="text-xs">↗</span>
              </a>
            </li>
            <li>
              <a href="https://getalby.com/alby-go" target="_blank" rel="noopener"
                 class="text-ink-soft hover:text-accent transition-colors inline-flex items-center gap-1">
                Alby Go <span aria-hidden="true" class="text-xs">↗</span>
              </a>
            </li>
          </ul>
        </div>

        <!-- Column 3 — Tech -->
        <div class="space-y-3">
          <p class="v4v-eyebrow">
            {{ lang === 'de' ? 'Technologie' : 'Technology' }}
          </p>
          <a
            href="https://lnbits.com"
            target="_blank" rel="noopener"
            class="block group"
          >
            <p class="text-xs text-ink-mute mb-2">{{ t('footer.poweredby') }}</p>
            <img
              :src="lnbitsLogo"
              alt="LNbits"
              class="h-5 sm:h-6 opacity-90 group-hover:opacity-100 transition-opacity"
            />
          </a>
          <p class="text-xs text-ink-mute leading-relaxed pt-2">
            {{ lang === 'de'
              ? 'Open-Source Lightning-Infrastruktur'
              : 'Open-source Lightning infrastructure' }}
          </p>
        </div>
      </div>

      <!-- bottom strip -->
      <div class="border-t border-line/30">
        <div class="max-w-5xl mx-auto px-6 py-5
                    flex flex-col sm:flex-row items-center justify-between
                    gap-3 text-xs text-ink-mute">
          <span class="tracking-wider uppercase">value4value.eu · for 21m.art</span>
          <a
            href="https://drshift.dev"
            target="_blank"
            rel="noopener"
            class="group inline-flex items-center gap-1 opacity-60 hover:opacity-100 transition-opacity"
          >
            {{ lang === 'de' ? 'Gebaut von' : 'Built by' }}
            <span class="text-ink-soft tracking-wide group-hover:text-accent transition-colors">DrShift</span>
            <svg viewBox="0 0 24 24" class="size-3 text-accent/70" fill="currentColor" aria-hidden="true">
              <path d="M13 2 4 14h6l-1 8 9-12h-6l1-8Z" />
            </svg>
            <span>{{ lang === 'de' ? 'für' : 'for' }}</span>
            <span class="text-ink-soft tracking-wide">Bloemelen</span>
          </a>
        </div>
      </div>
    </footer>
  </div>
</template>
