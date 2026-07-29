document.addEventListener('DOMContentLoaded', async () => {
  const summary = document.getElementById('user-summary');
  const title = document.getElementById('role-title');
  const description = document.getElementById('role-description');
  const logoutButton = document.getElementById('logout-button');

  try {
    const response = await fetch('/auth/me', { credentials: 'include' });
    if (!response.ok) {
      window.location.href = '/';
      return;
    }

    const user = await response.json();
    summary.textContent = `${user.username} — rôle ${user.role}`;

    if (user.role === 'admin') {
      title.textContent = 'Administration des utilisateurs';
      description.textContent = 'L’administrateur gère les comptes du Backoffice.';
    } else {
      title.textContent = 'Stock de votre agence';
      description.textContent = user.branch_name || `Agence n°${user.branch_id}`;
    }
  } catch {
    window.location.href = '/';
  }

  logoutButton.addEventListener('click', async () => {
    await fetch('/auth/logout', {
      method: 'POST',
      credentials: 'include',
    });
    window.location.href = '/';
  });
});
