document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('login-form');
  const errorDiv = document.getElementById('error-message');

  if (!form) return;

  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    errorDiv.style.display = 'none';
    errorDiv.textContent = '';

    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value;

    try {
      const response = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ username, password }),
      });

      if (response.ok) {
        window.location.href = 'app.html';
        return;
      }

      const data = await response.json().catch(() => ({}));
      errorDiv.textContent = data.detail || 'Erreur de connexion';
      errorDiv.style.display = 'block';
    } catch {
      errorDiv.textContent = 'Impossible de contacter le serveur';
      errorDiv.style.display = 'block';
    }
  });
});
