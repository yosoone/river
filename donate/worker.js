// Yoso donations: a Cloudflare Worker at donate.yoso.one.
//
// GET  /          the general donation page (amount, optional project)
// POST /checkout  turns the amount into a Stripe Checkout page in yen and sends
//                 the reader there; afterwards Stripe brings them back with a
//                 thank-you. River's download page posts here too.
//
// It needs one secret, set in Cloudflare (never in this file or the repo):
//   STRIPE_SECRET_KEY  a Stripe restricted key with 'Checkout Sessions: Write'
// See donate/README.md for the setup.

const VERSION = 'Beta 0.3';
const HOME = 'https://donate.yoso.one';
const ALLOWED_ORIGINS = [
  HOME, 'https://river.yoso.one', 'https://hub.yoso.one', 'https://yosoone.github.io',
];
const MIN_YEN = 100;        // Stripe's floor for yen is ¥50; ¥100 keeps fees sensible
const MAX_YEN = 1000000;
const SUGGEST = [500, 1000, 3000];
const LOCALES = ['en', 'ja', 'fr'];

// Projects a donation can be for. 'name' shows on Stripe's checkout; 'back' is
// where readers land afterwards. A form that sends no 'for' is River's.
const PROJECTS = {
  yoso:     { label: 'Wherever it’s needed', name: 'Donation to Yoso', back: `${HOME}/` },
  dojo:     { label: 'The creation of the dojo', name: 'Donation to the dojo', back: `${HOME}/` },
  river:    { label: 'River 川 · short texts', name: 'Donation to River 川', back: 'https://river.yoso.one/#book' },
  shinsei:  { label: 'Shinsei · paintings and scrolls', name: 'Donation to Shinsei', back: `${HOME}/` },
  yosokuro: { label: 'Yosokuro · photographs of Japan', name: 'Donation to Yosokuro', back: `${HOME}/` },
  on:       { label: 'On · the magazine', name: 'Donation to On', back: `${HOME}/` },
  one:      { label: 'The Vault · notes and essays', name: 'Donation to The Vault', back: `${HOME}/` },
};

function withStatus(url, status) {
  const u = new URL(url);
  u.searchParams.set('donation', status);
  return u.toString();
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === '/robots.txt') return new Response(ROBOTS, { headers: { 'content-type': 'text/plain; charset=utf-8' } });
    if (url.pathname === '/' && request.method === 'GET') {
      return new Response(page(url.searchParams.get('donation'), url.searchParams.get('for')), {
        headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' },
      });
    }
    if (url.pathname !== '/checkout') return Response.redirect(`${HOME}/`, 302);
    if (request.method !== 'POST') return Response.redirect(`${HOME}/`, 303);

    // Only accept forms sent from Yoso's sites.
    const origin = request.headers.get('Origin');
    if (origin && !ALLOWED_ORIGINS.includes(origin)) return new Response('Forbidden', { status: 403 });

    let form;
    try { form = await request.formData(); } catch { return Response.redirect(withStatus(`${HOME}/`, 'invalid'), 303); }
    const key = String(form.get('for') || 'river');
    const project = PROJECTS[key] ? key : 'yoso';
    const p = PROJECTS[project];
    const amount = parseInt(String(form.get('amount') || '').replace(/[^\d]/g, ''), 10);
    if (!Number.isFinite(amount) || amount < MIN_YEN || amount > MAX_YEN) return Response.redirect(withStatus(p.back, 'invalid'), 303);
    const lang = String(form.get('lang') || '');
    const locale = LOCALES.includes(lang) ? lang : 'auto';

    if (!env.STRIPE_SECRET_KEY) return Response.redirect(withStatus(p.back, 'error'), 303);

    const success = new URL(withStatus(p.back, 'thanks'));
    if (p.back.startsWith(HOME)) success.searchParams.set('for', project);
    const body = new URLSearchParams({
      mode: 'payment',
      submit_type: 'donate',
      locale,
      'line_items[0][quantity]': '1',
      'line_items[0][price_data][currency]': 'jpy',
      'line_items[0][price_data][unit_amount]': String(amount), // yen have no decimals
      'line_items[0][price_data][product_data][name]': p.name,
      'line_items[0][price_data][product_data][description]': 'Yoso · Miyazaki, Japan',
      'payment_intent_data[description]': `${p.name} (${project})`,
      'metadata[site]': project,
      success_url: success.toString(),
      cancel_url: p.back,
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
        return Response.redirect(withStatus(p.back, 'error'), 303);
      }
    } catch (e) {
      console.log('Stripe unreachable', String(e));
      return Response.redirect(withStatus(p.back, 'error'), 303);
    }
    return Response.redirect(session.url, 303);
  },
};

const ROBOTS = `# robots.txt for donate.yoso.one
# Search engines may index this site. AI model-training crawlers may not.
# Shared across all Yoso microsites; see the yoso-microsites skill.

User-agent: GPTBot
User-agent: ClaudeBot
User-agent: Google-Extended
User-agent: Applebot-Extended
User-agent: meta-externalagent
User-agent: CCBot
User-agent: Bytespider
Disallow: /

User-agent: *
Allow: /
`;

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const yen = (n) => '¥' + Number(n).toLocaleString('en');

// The page. Wording is a draft for Yoso to rewrite.
function page(status, forKey) {
  const chosen = PROJECTS[forKey] ? forKey : 'yoso';
  const flash = status === 'thanks'
    ? `<p class="flash" role="status">Thank you for your support. It means a great deal.</p>`
    : status === 'invalid'
      ? `<p class="flash bad" role="alert">Please enter an amount of ¥${MIN_YEN} or more.</p>`
      : status === 'error'
        ? `<p class="flash bad" role="alert">The donation didn’t go through and nothing was charged. Please try again.</p>`
        : '';
  const options = Object.entries(PROJECTS).map(([k, p]) =>
    `<option value="${k}"${k === chosen ? ' selected' : ''}>${esc(p.label)}</option>`).join('');
  const chips = SUGGEST.map((n) => `<button type="button" class="chip" data-yen="${n}">${yen(n)}</button>`).join('');
  return `<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Donate · Yoso</title>
<meta name="description" content="Support the work of Yoso, an artist in Miyazaki, Japan.">
<link rel="icon" href="https://river.yoso.one/images/yoso-mark.png">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Shippori+Mincho:wght@400;600&family=Zen+Kaku+Gothic+New:wght@400;500&display=swap">
<style>
*,*::before,*::after{box-sizing:border-box}
:root{--ground:#EEEDE8;--paper:#F6F5F1;--ink:#1C1C1A;--ink-2:#3A3A36;--muted:#5A5A55;--rule:#D3D1CA;--accent:#2F3E5C;--bad:#A33A2A;
--display:'Shippori Mincho','Hiragino Mincho ProN','Yu Mincho',Georgia,serif;--body:'Zen Kaku Gothic New','Hiragino Sans','Yu Gothic',system-ui,sans-serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--ground:#181816;--paper:#20201D;--ink:#ECEBE5;--ink-2:#C9C8C1;--muted:#9A998F;--rule:#34332F;--accent:#A9B8D6;--bad:#E59A8C;color-scheme:dark}}
:root[data-theme="dark"]{--ground:#181816;--paper:#20201D;--ink:#ECEBE5;--ink-2:#C9C8C1;--muted:#9A998F;--rule:#34332F;--accent:#A9B8D6;--bad:#E59A8C;color-scheme:dark}
body{margin:0;background:var(--ground);color:var(--ink);font-family:var(--body);font-size:16px;line-height:1.7}
a{color:var(--accent)}
a:focus-visible,button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:2px}
.wrap{max-width:640px;margin:0 auto;padding:0 max(16px,env(safe-area-inset-left,0px))}
.family-mark{display:block;width:48px;margin:24px auto 0;line-height:0}
.family-mark img{display:block;width:48px;height:48px}
header{padding:32px 0 8px;text-align:center}
header a{font-family:var(--display);font-size:22px;letter-spacing:.08em;text-decoration:none;color:var(--ink)}
main{padding:24px 0 48px}
h1{margin:0 0 14px;font-family:var(--display);font-weight:400;font-size:clamp(34px,7vw,48px);line-height:1.15}
.lead{margin:0 0 32px;color:var(--ink-2);font-size:17px}h1{margin-bottom:28px}
.flash{margin:0 0 24px;padding:14px 16px;border-left:3px solid var(--accent);background:var(--paper)}
.flash.bad{border-left-color:var(--bad)}
form.give{display:grid;gap:10px;padding:28px 0;border-top:1px solid var(--rule);border-bottom:1px solid var(--rule)}
label,.lbl{font-size:13px;letter-spacing:.06em;color:var(--muted)}
select,.amount input{min-height:44px;width:100%;min-width:0;font:inherit;font-size:16px;color:var(--ink);background:var(--paper);border:1px solid var(--rule);border-radius:8px;padding:0 12px}
.gap{margin-top:12px}
.chips{display:flex;flex-wrap:wrap;gap:8px}
.chip{min-height:44px;min-width:80px;padding:0 16px;font:inherit;font-size:15px;color:var(--ink-2);background:transparent;border:1px solid var(--rule);border-radius:8px;cursor:pointer}
.chip:hover{border-color:#9C761C;color:var(--ink)}
.chip[aria-pressed="true"]{border-color:#9C761C;color:var(--ink)}
.amount{display:flex;flex-wrap:wrap;gap:8px}
.amount .yen{display:grid;place-items:center;min-width:44px;border:1px solid var(--rule);border-radius:8px;background:var(--paper);color:var(--muted)}
.amount input{flex:1 1 140px;width:auto}
.amount button{min-height:44px;padding:0 24px;font:inherit;font-size:15px;letter-spacing:.06em;color:#F6F5F1;background:#4A4944;border:0;border-radius:8px;cursor:pointer;transition:background .35s ease,box-shadow .35s ease,color .35s ease}
.amount button:hover{background:#E1BA4B;color:#1C1C1A;box-shadow:0 0 0 4px rgba(225,186,75,.28),0 6px 22px -6px rgba(225,186,75,.28)}
.note{margin:4px 0 0;font-size:13px;color:var(--muted)}
.err{margin:0;font-size:14px;color:var(--bad)}
.err:empty{display:none}
.back{margin:28px 0 0;text-align:center;font-size:14px}
.back a{display:inline-flex;align-items:center;min-height:44px;padding:0 14px;color:var(--muted);text-decoration:none;border:1px solid transparent;border-radius:8px}
.back a:hover{color:var(--ink);border-color:var(--rule)}
footer{display:flex;flex-wrap:wrap;gap:12px;justify-content:space-between;margin-top:32px;padding:28px 0 48px;border-top:1px solid var(--rule);font-size:13px;color:var(--muted)}
footer p{margin:0}
</style>
</head>
<body>
<div class="wrap">
<span class="family-mark"><img src="https://river.yoso.one/images/yoso-mark.png" alt="Yoso" width="48" height="48"></span>
<header><a href="${HOME}/">Yoso</a></header>
<main>
<h1>Donate</h1>
${flash}
<form class="give" id="give" action="${HOME}/checkout" method="post" novalidate>
<label for="for">What it’s for</label>
<select id="for" name="for">${options}</select>
<span class="lbl gap" id="amt-l">Amount in yen</span>
<div class="chips" role="group" aria-labelledby="amt-l">${chips}</div>
<label for="amount">or type any amount</label>
<div class="amount"><span class="yen" aria-hidden="true">¥</span>
<input id="amount" name="amount" inputmode="numeric" pattern="[0-9]*" autocomplete="off" placeholder="1,000" aria-label="Amount in yen">
<button type="submit" id="go">Donate</button></div>
<p class="note">Paid through Stripe’s secure checkout. Minimum ¥${MIN_YEN}.</p>
<p class="err" id="err" role="alert"></p>
</form>
</main>
<p class="back" id="back" hidden><a href="#">← Back</a></p>
<footer><p>&copy; 2026 <a class="hub-link" href="https://hub.yoso.one">Yoso</a> · Miyazaki, Japan</p><p><span class="version" data-version>${VERSION}</span></p></footer>
</div>
<script>
(function(){
var f=document.getElementById('give'),a=document.getElementById('amount'),b=document.getElementById('go'),e=document.getElementById('err'),c=f.querySelectorAll('.chip');
function n(){return parseInt(a.value.replace(/[^0-9]/g,''),10)}
function y(v){return '¥'+Number(v).toLocaleString('en')}
function sync(){var v=n();b.textContent=v?'Donate '+y(v):'Donate';c.forEach(function(x){x.setAttribute('aria-pressed',String(Number(x.dataset.yen)===v))});e.textContent=''}
c.forEach(function(x){x.addEventListener('click',function(){a.value=Number(x.dataset.yen).toLocaleString('en');sync()})});
a.addEventListener('input',sync);sync();
f.addEventListener('submit',function(ev){var v=n();if(!v||v<${MIN_YEN}){ev.preventDefault();e.textContent='Please enter an amount of ¥${MIN_YEN} or more.';a.focus();return}a.value=String(v)});
// Back link: only for readers who arrived from one of Yoso's sites. The
// address is kept for the visit, so it survives the trip to Stripe and back.
var bk=document.getElementById('back'),HOMES={river:'https://river.yoso.one/',shinsei:'https://shinsei.yoso.one/',yosokuro:'https://yosokuro.yoso.one/',on:'https://on.yoso.one/',one:'https://one.yoso.one/'};
function ours(u){try{var h=new URL(u).hostname;return h!=='donate.yoso.one'&&(h==='yoso.one'||/\.yoso\.one$/.test(h)||h==='yosoone.github.io')}catch(x){return false}}
var from='';try{from=sessionStorage.getItem('yoso-from')||''}catch(x){}
if(ours(document.referrer)){from=document.referrer}
else if(!from){var k=new URLSearchParams(location.search).get('for');if(HOMES[k])from=HOMES[k]}
if(from){try{sessionStorage.setItem('yoso-from',from)}catch(x){}bk.querySelector('a').href=from;bk.hidden=false}
if(location.search){history.replaceState(null,'',location.pathname)}
})();
</script>
</body>
</html>`;
}
