# River donations (Stripe through Cloudflare)

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
2. Name it `river-donate` and choose **Deploy**.
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
