# Yoso donations (Stripe through Cloudflare)

`donate.yoso.one` is a small Cloudflare Worker (`worker.js`, deployed as `river-donate`). It does two things:

- **`/`** shows the general donation page: what the donation is for (wherever it's needed, the creation of the dojo, River, Shinsei, Yosokuro, On, The Vault), suggested amounts and an amount box. It has no mailing list (Yoso's choice). The projects are `PROJECTS` in `worker.js`.
- **`/checkout`** takes the amount and project from any of Yoso's sites and opens Stripe Checkout in yen. A form that sends no `for` is treated as River's.

The rest of this note covers River's own download page, which posts here too.


The download page (`river.yoso.one/#book`) has an amount box. When a reader presses **Donate**, the amount goes to a small Cloudflare Worker at `donate.yoso.one`. The Worker (`worker.js`) asks Stripe for a checkout page at exactly that amount, in yen, and sends the reader there in a new tab. After paying, Stripe brings them back to the download page with a thank-you. Nothing about the reader is stored on the site.

The Stripe key lives only in Cloudflare, never in this repo.

## One-time setup

### 1. Make a restricted Stripe key

1. In the Stripe Dashboard, go to **Developers › API keys**.
2. Under **Restricted keys**, choose **Create restricted key**.
3. Name it `River donations`.
4. Set **Checkout Sessions** to **Write**. Leave everything else as **None**.
5. Create it and copy the key (it starts with `rk_live_`). Keep it to paste in step 2 only.

A restricted key can only create checkout pages, so even if it leaked it could not move money or read customers.

### 2. Create the Worker in Cloudflare

1. In the Cloudflare dashboard, go to **Workers & Pages › Create › Create Worker**.
2. Name it `river-donate` and choose **Deploy**. (Already done; to update, open the Worker, choose **Edit code**, paste in `worker.js` and **Deploy**.)
3. Choose **Edit code**, replace everything with the contents of `worker.js`, then **Deploy**.
4. In the Worker's **Settings › Variables and Secrets**, choose **Add**, type **Secret**, name `STRIPE_SECRET_KEY`, and paste the key from step 1. Save and deploy.
5. In **Settings › Domains & Routes**, choose **Add › Custom domain** and enter `donate.yoso.one`.

(From a terminal instead: `npx wrangler deploy` in this folder, then `npx wrangler secret put STRIPE_SECRET_KEY`.)

### 3. Switch it on in the site

In `index.html`, set:

```js
const DONATE_ENDPOINT = 'https://donate.yoso.one/checkout';
```

Until this is set, the download page says 'Donations will open here soon'.

## Settings in `worker.js`

- `MIN_YEN` (¥100) and `MAX_YEN` (¥1,000,000): the allowed range. Stripe's own minimum for yen is ¥50.
- `ALLOWED_ORIGINS`: only forms from these sites are accepted.
- The checkout shows 'Donation to River 川', and the payment's description and metadata say `river`, so River donations are easy to find in Stripe.

The suggested amounts on the page are `DONATE_SUGGEST` in `index.html`.

## Testing

To test without real money, use a test-mode restricted key (`rk_test_…`) in the Worker and pay with Stripe's test card `4242 4242 4242 4242`. Swap in the live key afterwards.

## Contact form (River)

River's contact page (`river.yoso.one/#contact`) posts to `/contact` on this Worker, which emails the message to Yoso, with the reader's address as Reply-To. Nothing is stored. Until the steps below are done, the page says 'The contact form opens here soon'; it switches itself on once `/contact/ready` answers `{"ready":true}`.

Cloudflare's Email Service can send from a Worker to your own verified address on the free plan.[^cf]

1. **Email Routing on yoso.one.** In the Cloudflare dashboard, open the `yoso.one` zone › **Email › Email Routing**, enable it, and add your own address under **Destination addresses**. Confirm it from the email Cloudflare sends you.
2. **The sending binding.** Deploy this folder with `npx wrangler deploy`: `wrangler.toml` already declares a `send_email` binding named `EMAIL`. (In the dashboard instead: the Worker › **Settings › Bindings › Add › Send email**, name `EMAIL`.)
3. **Your address, as a secret.** `npx wrangler secret put CONTACT_TO` and type your address (dashboard: **Settings › Variables and Secrets › Add › Secret**, name `CONTACT_TO`). It never appears in the repo or on the site.
4. **Paste the new `worker.js`** if you deploy from the dashboard, then **Deploy**.
5. **Test:** open `https://donate.yoso.one/contact/ready`. It should show `{"ready":true}`; then send yourself a message from River's contact page.

Messages arrive from `river@yoso.one` with the subject 'River 川 · message from …'. A hidden field catches simple spam bots; if spam becomes a problem, Cloudflare Turnstile can be added to the form.

[^cf]: Cloudflare, '[Email Service](https://developers.cloudflare.com/email-routing/email-workers/send-email-workers/)' and '[Workers API: send emails](https://developers.cloudflare.com/email-service/api/send-emails/workers-api/)', *Cloudflare Docs*, accessed 27 October 2026.
