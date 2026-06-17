// HTMX configuration: CSRF + native View Transitions.
(function () {
  function getCookie(name) {
    const m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? decodeURIComponent(m.pop()) : '';
  }

  document.addEventListener('htmx:configRequest', function (evt) {
    evt.detail.headers['X-CSRFToken'] = getCookie('csrftoken');
  });

  // Opt into the View Transitions API where available, for quiet, upscale motion.
  if (window.htmx) {
    htmx.config.globalViewTransitions = true;
  }
})();
