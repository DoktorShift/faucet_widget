<script setup>
import { computed } from 'vue'

// Logos bundled by Vite — eager-import everything in assets/wallets so we
// get hashed asset paths at build time.
const logoModules = import.meta.glob('@/assets/wallets/*.{svg,png}', {
  eager: true,
  query: '?url',
  import: 'default',
})

function logoFor(filename) {
  if (!filename) return null
  const match = Object.entries(logoModules).find(([k]) => k.endsWith(`/${filename}`))
  return match ? match[1] : null
}

const props = defineProps({
  wallets: { type: Array, required: true },
})

const items = computed(() =>
  props.wallets.map((w, i) => ({
    ...w,
    logoUrl: logoFor(w.logo),
    initials: w.name.split(' ').map((p) => p[0]).join('').slice(0, 2).toUpperCase(),
    index: i + 1,
  })),
)
</script>

<template>
  <ul class="space-y-3 sm:space-y-4">
    <li v-for="w in items" :key="w.name">
      <a
        :href="w.url"
        target="_blank"
        rel="noopener noreferrer"
        class="relative group block overflow-hidden
               rounded-card bg-bg-soft
               ring-1 ring-line/40 hover:ring-accent/50
               transition-all duration-200
               focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/70"
      >
        <!-- Hover glow — subtle radial accent that emerges from the left -->
        <span
          aria-hidden="true"
          class="absolute inset-0 opacity-0 group-hover:opacity-100
                 transition-opacity duration-300
                 bg-[radial-gradient(circle_at_0%_50%,rgba(247,147,26,0.12),transparent_45%)]"
        />

        <!-- Left orange bar — appears on hover -->
        <span
          aria-hidden="true"
          class="absolute left-0 top-0 bottom-0 w-1 bg-accent
                 scale-y-0 group-hover:scale-y-100 origin-center
                 transition-transform duration-300"
        />

        <div class="relative flex items-center gap-5 sm:gap-6 p-5 sm:p-6">

          <!-- Logo plate -->
          <div class="shrink-0 size-16 sm:size-20 rounded-card
                      bg-bg ring-1 ring-line/60
                      grid place-items-center
                      group-hover:ring-accent/30 transition-colors">
            <img
              v-if="w.logoUrl"
              :src="w.logoUrl"
              :alt="`${w.name} logo`"
              loading="lazy"
              class="size-full object-contain p-2.5"
            />
            <span v-else
                  class="text-accent font-semibold text-lg tracking-tight">
              {{ w.initials }}
            </span>
          </div>

          <!-- Name + tagline -->
          <div class="min-w-0 flex-1">
            <div class="flex items-center gap-2 mb-1">
              <span class="font-medium text-ink text-base sm:text-lg leading-tight">
                {{ w.name }}
              </span>
            </div>
            <p class="text-sm text-ink-soft leading-snug">{{ w.tagline }}</p>
          </div>

          <!-- Arrow — animates on hover -->
          <span
            aria-hidden="true"
            class="shrink-0 text-ink-mute text-xl
                   group-hover:text-accent
                   transform group-hover:translate-x-1
                   transition-all duration-200"
          >↗</span>
        </div>
      </a>
    </li>
  </ul>
</template>
