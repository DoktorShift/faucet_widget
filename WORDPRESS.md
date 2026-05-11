# WordPress integration

Three ways to put the **"Get X sats"** button on your WordPress site.
Each one is fully working. Start with Option A. Fall back if your theme
fights you.

> Replace `https://value4value.eu` with your own deployed URL everywhere
> below.

---

## Option A: drop-in script (best UX)

What you get: button on the post, click opens a modal, QR appears, sats fly.
No external redirect. Works in any page or sidebar.

In the WordPress editor, add a **Custom HTML** block and paste:

```html
<script src="https://value4value.eu/embed.js" defer></script>

<button data-v4v-claim
        style="display:inline-flex;align-items:center;gap:.5rem;
               background:#f7931a;color:#1f1f1f;border:0;cursor:pointer;
               padding:.85rem 1.6rem;border-radius:8px;
               font-weight:500;font-size:1rem;letter-spacing:.03em;">
  ⚡ Hol dir 21 sats
</button>
```

Multiple buttons on the same page work. Trigger from elsewhere:

```html
<a href="#" onclick="event.preventDefault(); window.V4V.open();">
  Click here to claim
</a>
```

### How to verify

1. Save the post, open in a private window.
2. DevTools → Network → reload. `embed.js` should load with HTTP 200.
3. Click the button. A centered, dark + orange modal opens.

### Troubleshooting

| Console says... | Cause | Fix |
| --- | --- | --- |
| `Failed to load embed.js` | DNS/tunnel down | Check your Cloudflared tunnel |
| `Refused to load script ... CSP` | Hardening plugin set CSP | Use Option B |
| Button does nothing, no errors | Theme stripped `data-v4v-claim` | Use the `.v4v-claim` class fallback (see below) |
| `CORS error` on /api/claim | `app.cors_origins` missing your host | Add your site to `config.toml` |

---

## Option B: enqueue via theme `functions.php`

Use this if Option A is blocked by a CSP, `wp_kses`, or a security plugin.
The script registers through the standard WordPress asset pipeline, so
sanitizers never see it.

In your **child theme's `functions.php`** (or Code Snippets plugin):

```php
add_action('wp_enqueue_scripts', function () {
    wp_enqueue_script(
        'value4value-embed',
        'https://value4value.eu/embed.js',
        [],     // no deps
        null,   // immutable hashed asset, no version query
        true    // load in footer
    );
});
```

Then in the post you only need the button (no script tag, so any sanitizer
leaves it alone):

```html
<button class="wp-block-button__link v4v-claim"
        style="background:#f7931a;color:#1f1f1f">
  ⚡ Hol dir 21 sats
</button>
```

The embed auto-binds both `[data-v4v-claim]` and `.v4v-claim`. The class
form survives even aggressive sanitisers.

---

## Option C: plain link (zero JavaScript, always works)

Use this when nothing else will. The user gets sent to your landing page,
where the full claim flow lives. No embed, no scripts, no fuss.

```html
<a href="https://value4value.eu/?lang=de"
   style="display:inline-flex;align-items:center;gap:.5rem;
          background:#f7931a;color:#1f1f1f;text-decoration:none;
          padding:.85rem 1.6rem;border-radius:8px;
          font-weight:500;font-size:1rem;letter-spacing:.03em;">
  ⚡ Hol dir 21 sats
</a>
```

Survives any sanitiser, any CSP, any security plugin. The cost: one extra
page hop. Recommended as a safety net even when Option A works for you.

---

## Language

The script picks the language from your backend's `app.default_lang` config.
Override per page:

```html
<!-- whole-page override -->
<script src="https://value4value.eu/embed.js"
        data-v4v-lang="en" defer></script>

<!-- one link (Option C) -->
<a href="https://value4value.eu/?lang=en">⚡ Get 21 sats</a>
```

Supported: `de`, `en`.

---

## Compatibility matrix

| Plugin / setting | A: embed | B: enqueue | C: link |
| :--- | :---: | :---: | :---: |
| Default Gutenberg | yes | yes | yes |
| Yoast SEO | yes | yes | yes |
| Wordfence (default) | yes | yes | yes |
| Wordfence + "block external JS" | no | yes | yes |
| iThemes Security | yes | yes | yes |
| WP Rocket / W3 Total Cache | yes | yes | yes |
| Membership plugins (RCP, etc.) | yes | yes | yes |
| Strict CSP (`script-src 'self'`) | no | no | yes |
| WordPress.com (non-Business plan) | no | n/a | yes |
