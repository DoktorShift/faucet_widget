<script setup>
import { useI18n, SUPPORTED_LANGS } from '@/i18n.js'

const { lang, setLang } = useI18n()
</script>

<template>
  <!-- Pill with backdrop blur so it stays readable when overlaid on the
       hero banner image. Larger touch targets on mobile (min 36px). -->
  <div class="inline-flex items-center rounded-full
              bg-bg/55 backdrop-blur-md
              ring-1 ring-white/15
              shadow-[0_4px_14px_-6px_rgba(0,0,0,0.6)]
              p-0.5 text-[0.72rem]">
    <button
      v-for="code in SUPPORTED_LANGS"
      :key="code"
      type="button"
      :aria-pressed="lang === code"
      :aria-label="code === 'de' ? 'Deutsch' : 'English'"
      :class="[
        'min-w-[2.5rem] h-8 sm:h-7 px-3 rounded-full',
        'uppercase tracking-headline font-medium',
        'transition-all duration-150',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/70',
        lang === code
          ? 'bg-accent text-bg shadow-sm'
          : 'text-ink/85 hover:text-ink',
      ]"
      @click="setLang(code)"
    >
      {{ code }}
    </button>
  </div>
</template>
