// JS pour forcer le rechargement après suppression d'un patient via formulaire AJAX

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('form[action$="/delete"]').forEach(function(form) {
    form.addEventListener('submit', function(e) {
      // Si le formulaire est envoyé en AJAX, intercepter
      if (form.hasAttribute('data-ajax')) {
        e.preventDefault();
        fetch(form.action, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Content-Type': 'application/x-www-form-urlencoded',
          },
          body: new URLSearchParams(new FormData(form)),
        })
        .then(resp => {
          if (resp.redirected) {
            window.location.href = resp.url;
          } else if (resp.ok) {
            window.location.reload();
          }
        });
      }
    });
  });
});
