document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('login-form');
  const errorDiv = document.getElementById('error-message');
  const submitButton = form?.querySelector('button[type="submit"]');

  if (!form || !errorDiv || !submitButton) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorDiv.hidden = true;
    errorDiv.textContent = '';

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;
    const originalLabel = submitButton.textContent;

    submitButton.disabled = true;
    submitButton.textContent = 'Connexion…';

    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.detail || 'Identifiant ou mot de passe incorrect.');
      }

      const data = await response.json();
      window.location.href = data.user?.role === 'admin' ? '/users.html' : '/stock.html';
    } catch (error) {
      errorDiv.textContent = error.message || 'Impossible de contacter le serveur.';
      errorDiv.hidden = false;
      submitButton.disabled = false;
      submitButton.textContent = originalLabel;
    }
  });
});
