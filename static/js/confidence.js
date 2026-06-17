// One-gesture confidence slider: live-update the % label as the user drags.
(function () {
  function bind() {
    document.querySelectorAll('[data-confidence-input]').forEach(function (input) {
      const output = document.querySelector('[data-confidence-output]');
      if (!output) return;
      const sync = function () { output.textContent = input.value; };
      input.addEventListener('input', sync);
      sync();
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
