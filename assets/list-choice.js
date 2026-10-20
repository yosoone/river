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
 * Wording comes from data- attributes on the <fieldset>, so a multilingual site can
 * change them and call window.yosoListChoice.refresh().
 */
(function () {
  "use strict";

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
    ".lc-hidden{display:none !important}";

  function addStyle() {
    if (document.getElementById("lc-style")) return;
    var s = document.createElement("style");
    s.id = "lc-style";
    s.textContent = css;
    document.head.appendChild(s);
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
    fs.appendChild(msg);

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
      // The form posts to Buttondown in a new tab; afterwards this page goes back to step 1.
      msg.textContent = "";
      setTimeout(function () {
        state.step = "email";
        email.value = "";
        Array.prototype.forEach.call(fs.querySelectorAll('input[type="checkbox"]'), function (b) { b.checked = b.defaultChecked; });
        render();
      }, 0);
    });

    change.addEventListener("click", function () {
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
