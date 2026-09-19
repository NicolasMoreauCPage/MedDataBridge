// JS pour forcer le rechargement après suppression d'un patient via formulaire AJAX

document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('form[action$="/delete"]').forEach(function(form) {
    form.addEventListener('submit', async function(e) {
      // Si le formulaire est envoyé en AJAX, intercepter
      if (form.hasAttribute('data-ajax')) {
        e.preventDefault();
        try {
          const { response } = await window.medbridgeHttp.request(form.action, {
            method: 'POST',
            headers: {
              'X-Requested-With': 'XMLHttpRequest',
              'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: new URLSearchParams(new FormData(form)),
          });
          if (response.redirected) {
            window.location.href = response.url;
          } else {
            window.location.reload();
          }
        } catch (error) {
          window.NotificationSystem?.error?.(`Suppression impossible : ${error.message}`);
          console.error('Erreur de suppression patient:', error);
        }
      }
    });
  });
});
