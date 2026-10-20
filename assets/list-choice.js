/* Newsletter choice for Yoso's mailing list.
 *
 * The same file is used on every site (assets/list-choice.js).
 * The form stays a plain HTML form that posts to Buttondown. Each newsletter is a
 * tick-box named "tag"; Buttondown applies every ticked box as a tag.
 *
 * With this script: step 1 asks only for the email address and the button reads
 * 'Continue'; step 2 shows the tick-boxes, with this site's own newsletter already
 * ticked, and the button reads 'Subscribe'. Without the script the boxes simply
 * show under the email field and the form still works.
 *
 * Signing up: when Subscribe is pressed, the script sends the address and ticked
 * newsletters to the Yoso forms Worker (https://forms.yoso.one/subscribe), which adds the
 * reader to Buttondown; Buttondown then emails them to confirm. No new tab opens. A
 * mostly invisible Cloudflare Turnstile check, added by this script, keeps bots out.
 * If the Worker cannot be reached, the reader is asked to press Subscribe again, and
 * that press posts the form straight to Buttondown in a new tab, as before.
 *
 * Wording comes from data- attributes on the <fieldset>, so a multilingual site can
 * change them and call window.yosoListChoice.refresh(). Extra keys for the sign-up:
 * data-sending, data-done, data-retry, data-error.
 */
(function () {
  "use strict";

  var ENDPOINT = "https://forms.yoso.one/subscribe";
  var SITEKEY = "0x4AAAAAAFeWKK51BEJbKJSu"; // Turnstile widget 'Yoso forms' (public key)
  var TS_SRC = "https://challenges.cloudflare.com/turnstile/v0/api.js";

  var css =
    ".list-choice{border:0;margin:16px 0 0;padding:0;min-width:0}" +
    ".list-choice legend{padding:0;margin:0 0 8px;font-weight:600}" +
    ".list-choice .lc-box{display:flex;align-items:flex-start;gap:12px;min-height:44px;padding:10px 0;" +
    "border-top:1px solid color-mix(in srgb,currentColor 18%,transparent);cursor:pointer;line-height:1.4;text-align:left}" +
    ".list-choice .lc-box:last-of-type{border-bottom:1px solid color-mix(in srgb,currentColor 18%,transparent)}" +
    ".list-choice input[type=checkbox]{flex:none;width:20px;height:20px;margin:1px 0 0;accent-color:currentColor;cursor:pointer}" +
    ".list-choice input[type=checkbox]:focus-visible{outline:2px solid currentColor;outline-offset:3px}" +
    ".list-choice .lc-name{display:block;font-weight:600}" +
    ".list-choice .lc-desc{display:block;opacity:.75;font-size:.92em}" +
    ".lc-as{margin:0 0 4px;overflow-wrap:anywhere}" +
    "form .lc-as button.lc-change{display:inline;width:auto;font:inherit;letter-spacing:inherit;text-transform:none;color:inherit;background:none;border:0;border-radius:0;box-shadow:none;padding:0 2px;margin:0;min-height:44px;text-decoration:underline;cursor:pointer}" +
    "form .lc-as button.lc-change:focus-visible{outline:2px solid currentColor;outline-offset:2px}" +
    ".lc-msg{margin:8px 0 0;min-height:1.4em;font-size:.92em}" +
    ".lc-ts:empty{display:none}.lc-ts{margin:10px 0 0}" +
    ".lc-hidden{display:none !important}";

  function addStyle() {
    if (document.getElementById("lc-style")) return;
    var s = document.createElement("style");
    s.id = "lc-style";
    s.textContent = css;
    document.head.appendChild(s);
  }

  // Turnstile: load Cloudflare's script once (or reuse it if the page already has it),
  // then call back when window.turnstile is ready. Gives up quietly after 20 seconds.
  var tsWaiting = [];
  function withTurnstile(cb) {
    if (window.turnstile) { cb(window.turnstile); return; }
    tsWaiting.push(cb);
    if (tsWaiting.length > 1) return;
    if (!document.querySelector('script[src^="' + TS_SRC + '"]')) {
      var sc = document.createElement("script");
      sc.src = TS_SRC + "?render=explicit";
      sc.async = true;
      document.head.appendChild(sc);
    }
    var tries = 0;
    var timer = setInterval(function () {
      if (window.turnstile || ++tries > 100) {
        clearInterval(timer);
        var t = window.turnstile, list = tsWaiting;
        tsWaiting = [];
        if (t) list.forEach(function (f) { f(t); });
      }
    }, 200);
  }

  // Waits (up to about 8 seconds) for the widget's token.
  function tokenFor(box, done) {
    var tries = 0;
    (function look() {
      var t = window.turnstile, id = box.getAttribute("data-ts-id"), tok = "";
      if (t && id) { try { tok = t.getResponse(id) || ""; } catch (e) { tok = ""; } }
      if (tok || ++tries > 40) done(tok);
      else setTimeout(look, 200);
    })();
  }

  var forms = [];

  function word(fs, key, fallback) {
    return fs.getAttribute("data-" + key) || fallback;
  }

  function setup(form) {
    var fs = form.querySelector("fieldset[data-list-choice]");
    var email = form.querySelector('input[name="email"]');
    var button = form.querySelector('button[type="submit"], input[type="submit"]');
    if (!fs || !email || !button) return;

    // Everything that belongs to the email step: the email field's own row (or the field
    // and its label when there is no row) plus any element marked data-step="email".
    var emailRow = email.closest(".list-row, .sub-row") || email;
    var label = form.querySelector('label[for="' + email.id + '"]');
    var stepEmail = [email];
    if (label) stepEmail.push(label);
    Array.prototype.forEach.call(form.querySelectorAll('[data-step="email"]'), function (el) { stepEmail.push(el); });

    // The 'Signing up as … Change' line shown on the choice step.
    var as = document.createElement("p");
    as.className = "lc-as lc-hidden";
    as.setAttribute("aria-live", "polite");
    var asText = document.createElement("span");
    var change = document.createElement("button");
    change.type = "button";
    change.className = "lc-change";
    as.appendChild(asText);
    as.appendChild(document.createTextNode(" "));
    as.appendChild(change);
    fs.parentNode.insertBefore(as, fs);

    var msg = document.createElement("p");
    msg.className = "lc-msg";
    msg.setAttribute("role", "status");
    fs.parentNode.insertBefore(msg, fs.nextSibling);

    // The Turnstile widget sits in the choice step; it only shows if Cloudflare needs the
    // reader to prove they are human.
    var tsBox = document.createElement("div");
    tsBox.className = "lc-ts";
    fs.appendChild(tsBox);
    withTurnstile(function (t) {
      try {
        tsBox.setAttribute("data-ts-id", t.render(tsBox, { sitekey: SITEKEY, appearance: "interaction-only" }));
      } catch (e) { /* the fallback below still works */ }
    });
    var direct = false;   // true after the Worker failed: the next press posts to Buttondown

    // When the button shares a row with the email field, the whole row (which carries the
    // site's button styling) moves under the boxes on the choice step, minus the email field.
    var buttonInRow = emailRow !== email && emailRow.contains(button);
    var rowHome = emailRow.parentNode;
    var rowNext = emailRow.nextSibling;

    var state = { step: "email" };

    function setButton(text) {
      if (button.tagName === "INPUT") button.value = text; else button.textContent = text;
    }

    function render() {
      var choosing = state.step === "choose";
      stepEmail.forEach(function (el) { el.classList.toggle("lc-hidden", choosing); });
      fs.classList.toggle("lc-hidden", !choosing);
      as.classList.toggle("lc-hidden", !choosing);
      if (buttonInRow) {
        if (choosing) fs.parentNode.insertBefore(emailRow, fs.nextSibling);
        else rowHome.insertBefore(emailRow, rowNext);
      }
      asText.textContent = word(fs, "as", "Signing up as") + " " + email.value.trim();
      change.textContent = word(fs, "change", "Change");
      setButton(choosing ? word(fs, "subscribe", "Subscribe") : word(fs, "continue", "Continue"));
    }

    function ticked() {
      return Array.prototype.some.call(fs.querySelectorAll('input[type="checkbox"]'), function (b) { return b.checked; });
    }

    form.addEventListener("submit", function (e) {
      if (state.step === "email") {
        e.preventDefault();
        if (!email.checkValidity()) { email.reportValidity(); return; }
        state.step = "choose";
        direct = false;
        msg.textContent = "";
        render();
        var first = fs.querySelector('input[type="checkbox"]');
        if (first) first.focus();
        return;
      }
      if (!ticked()) {
        e.preventDefault();
        msg.textContent = word(fs, "none", "Tick at least one newsletter.");
        var box = fs.querySelector('input[type="checkbox"]');
        if (box) box.focus();
        return;
      }
      if (direct) {
        // Fallback: the form posts straight to Buttondown in a new tab, as it does without
        // this script; afterwards this page goes back to step 1.
        direct = false;
        msg.textContent = "";
        setTimeout(reset, 0);
        return;
      }
      e.preventDefault();
      if (state.sending) return;
      state.sending = true;
      button.disabled = true;
      msg.textContent = word(fs, "sending", "Signing you up…");
      tokenFor(tsBox, function (token) {
        var data = new FormData();
        data.append("email", email.value.trim());
        Array.prototype.forEach.call(fs.querySelectorAll('input[name="tag"]:checked'), function (b) { data.append("tag", b.value); });
        data.append("cf-turnstile-response", token);
        fetch(ENDPOINT, { method: "POST", body: data })
          .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { return r.ok && j.ok; }); })
          .catch(function () { return false; })
          .then(function (ok) {
            state.sending = false;
            button.disabled = false;
            try { if (window.turnstile && tsBox.getAttribute("data-ts-id")) window.turnstile.reset(tsBox.getAttribute("data-ts-id")); } catch (e2) {}
            if (ok) {
              reset();
              msg.textContent = word(fs, "done", "Thank you. Buttondown will email you to confirm.");
            } else {
              direct = true;
              msg.textContent = word(fs, "retry", "That didn’t go through. Press Subscribe again to sign up on Buttondown instead.");
            }
          });
      });
    });

    function reset() {
      state.step = "email";
      email.value = "";
      Array.prototype.forEach.call(fs.querySelectorAll('input[type="checkbox"]'), function (b) { b.checked = b.defaultChecked; });
      render();
    }

    change.addEventListener("click", function () {
      direct = false;
      msg.textContent = "";
      state.step = "email";
      render();
      email.focus();
    });

    forms.push(render);
    render();
  }

  function start() {
    addStyle();
    Array.prototype.forEach.call(document.querySelectorAll("form"), function (f) {
      if (f.querySelector("fieldset[data-list-choice]")) setup(f);
    });
  }

  window.yosoListChoice = { refresh: function () { forms.forEach(function (r) { r(); }); } };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
