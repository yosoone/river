// River 川 donations: a Cloudflare Worker between the download page and Stripe.
//
// The download page (river.yoso.one/#book) posts the amount the reader typed
// to https://donate.yoso.one/checkout. This Worker asks Stripe for a Checkout
// page at exactly that amount, in yen, and sends the reader there. After paying,
// Stripe brings them back to the download page with a thank-you.
//
// It needs one secret, set in Cloudflare (never in this file or the repo):
//   STRIPE_SECRET_KEY  a Stripe restricted key with 'Checkout Sessions: Write'
// See donate/README.md for the setup.

const SITE = 'https://river.yoso.one';
const ALLOWED_ORIGINS = [SITE, 'https://yosoone.github.io'];
const MIN_YEN = 100;        // Stripe's floor for yen is ¥50; ¥100 keeps fees sensible
const MAX_YEN = 1000000;
const LOCALES = ['en', 'ja', 'fr'];

const back = (status) => Response.redirect(`${SITE}/?donation=${status}#book`, 303);

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname !== '/checkout') {
      return new Response('River 川 donations. https://river.yoso.one', { status: 404 });
    }
    if (request.method !== 'POST') return Response.redirect(`${SITE}/#book`, 303);

    // Only accept forms sent from the River site.
    const origin = request.headers.get('Origin');
    if (origin && !ALLOWED_ORIGINS.includes(origin)) {
      return new Response('Forbidden', { status: 403 });
    }

    let form;
    try { form = await request.formData(); } catch { return back('invalid'); }
    const amount = parseInt(String(form.get('amount') || '').replace(/[^\d]/g, ''), 10);
    if (!Number.isFinite(amount) || amount < MIN_YEN || amount > MAX_YEN) return back('invalid');
    const lang = String(form.get('lang') || '');
    const locale = LOCALES.includes(lang) ? lang : 'auto';

    if (!env.STRIPE_SECRET_KEY) return back('error');

    const body = new URLSearchParams({
      mode: 'payment',
      submit_type: 'donate',
      locale,
      'line_items[0][quantity]': '1',
      'line_items[0][price_data][currency]': 'jpy',
      'line_items[0][price_data][unit_amount]': String(amount), // yen have no decimals
      'line_items[0][price_data][product_data][name]': 'Donation to River 川',
      'line_items[0][price_data][product_data][description]': 'Short texts by Yoso · river.yoso.one',
      'payment_intent_data[description]': 'River 川 donation',
      'metadata[site]': 'river',
      success_url: `${SITE}/?donation=thanks#book`,
      cancel_url: `${SITE}/#book`,
    });

    let session;
    try {
      const r = await fetch('https://api.stripe.com/v1/checkout/sessions', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${env.STRIPE_SECRET_KEY}`,
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body,
      });
      session = await r.json();
      if (!r.ok || !session.url) {
        console.log('Stripe error', r.status, session && session.error && session.error.message);
        return back('error');
      }
    } catch (e) {
      console.log('Stripe unreachable', String(e));
      return back('error');
    }
    return Response.redirect(session.url, 303);
  },
};
