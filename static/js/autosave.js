// Quiet, debounced auto-save for the compose form. No framework.
// First save creates exactly one draft; the server returns its id via the
// `draftSaved` HX-Trigger, which we write back into the hidden #entry-id field
// so subsequent saves target the same draft.
(function () {
  const DEBOUNCE_MS = 1200;

  function init() {
    const form = document.getElementById('compose-form');
    if (!form) return;

    const url = form.dataset.autosaveUrl;
    const entryId = document.getElementById('entry-id');
    let timer = null;

    async function save() {
      const data = new FormData(form);
      try {
        const resp = await fetch(url, {
          method: 'POST',
          body: data,
          headers: { 'X-Requested-With': 'XMLHttpRequest', 'HX-Request': 'true' },
        });
        if (resp.ok) {
          const newId = resp.headers.get('HX-Trigger');
          if (newId && entryId && !entryId.value) {
            try {
              const parsed = JSON.parse(newId);
              if (parsed.draftSaved && parsed.draftSaved.id) {
                entryId.value = parsed.draftSaved.id;
              }
            } catch (e) { /* header not JSON; ignore */ }
          }
          const status = document.getElementById('autosave-status');
          if (status) status.outerHTML = await resp.text();
        }
      } catch (e) {
        // Stay silent; the next keystroke retries. Never lose the user's text.
      }
    }

    function schedule() {
      if (timer) clearTimeout(timer);
      timer = setTimeout(save, DEBOUNCE_MS);
    }

    form.addEventListener('input', schedule);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
