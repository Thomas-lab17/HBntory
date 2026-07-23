// Gestion des utilisateurs - page admin
document.addEventListener('DOMContentLoaded', async () => {
  const userInfo = document.getElementById('user-info');
  const errorDiv = document.getElementById('error-message');
  const successDiv = document.getElementById('success-message');
  const logoutBtn = document.getElementById('logout-btn');
  const tableBody = document.getElementById('users-table-body');
  const createForm = document.getElementById('create-user-form');

  // Attach event delegation immediately (more reliable)
  tableBody.addEventListener('click', handleTableClick);

  // Vérifie l'authentification et le rôle admin
  try {
    const res = await fetch('/auth/me', { credentials: 'include' });
    if (!res.ok) {
      window.location.href = 'index.html';
      return;
    }
    const user = await res.json();
    if (user.role !== 'admin') {
      window.location.href = 'index.html';
      return;
    }
    userInfo.textContent = `Connecté en tant que ${user.username} (Admin)`;
  } catch (e) {
    window.location.href = 'index.html';
    return;
  }

  // Logout
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async () => {
      await fetch('/auth/logout', { method: 'POST', credentials: 'include' });
      window.location.href = 'index.html';
    });
  }

  // Gestion des clics sur les boutons d'action (event delegation)
  async function handleTableClick(e) {
    const btn = e.target.closest('button');
    if (!btn) return;

    const id = btn.getAttribute('data-id');
    const td = btn.parentElement;

    errorDiv.style.display = 'none';
    successDiv.style.display = 'none';

    // Disable all action buttons in this row during request
    td.querySelectorAll('button').forEach(b => b.disabled = true);

    try {
      if (btn.classList.contains('btn-delete')) {
        if (!confirm('Supprimer cet utilisateur ?')) {
          td.querySelectorAll('button').forEach(b => b.disabled = false);
          return;
        }

        const res = await fetch(`/users/${id}`, {
          method: 'DELETE',
          credentials: 'include'
        });
        if (res.ok) {
          successDiv.textContent = 'Utilisateur supprimé';
          successDiv.style.display = 'block';
          await loadUsers();
        } else {
          errorDiv.textContent = 'Erreur lors de la suppression';
          errorDiv.style.display = 'block';
          td.querySelectorAll('button').forEach(b => b.disabled = false);
        }
      }

      if (btn.classList.contains('btn-change-pwd')) {
        const newPassword = prompt('Nouveau mot de passe :');
        if (!newPassword) {
          td.querySelectorAll('button').forEach(b => b.disabled = false);
          return;
        }

        const res = await fetch(`/users/${id}/password`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ new_password: newPassword })
        });
        if (res.ok) {
          successDiv.textContent = 'Mot de passe modifié';
          successDiv.style.display = 'block';
        } else {
          errorDiv.textContent = 'Erreur lors du changement de mot de passe';
          errorDiv.style.display = 'block';
        }
        td.querySelectorAll('button').forEach(b => b.disabled = false);
      }

      if (btn.classList.contains('btn-change-branch')) {
        // Affiche un select inline pour changer d'agence
        const currentBranch = td.parentElement.children[1].textContent.trim();
        const originalHTML = td.innerHTML;

        td.innerHTML = `
          <select class="branch-select">
            <option value="1" ${currentBranch === '1' ? 'selected' : ''}>Paris</option>
            <option value="2" ${currentBranch === '2' ? 'selected' : ''}>Lyon</option>
          </select>
          <button class="btn-small">Valider</button>
          <button class="btn-small">Annuler</button>
        `;

        const select = td.querySelector('.branch-select');
        const buttons = td.querySelectorAll('.btn-small');
        const validateBtn = buttons[0];
        const cancelBtn = buttons[1];

        if (!validateBtn || !cancelBtn) {
          errorDiv.textContent = 'Erreur interne';
          errorDiv.style.display = 'block';
          return;
        }

        validateBtn.addEventListener('click', async () => {
          const newBranch = parseInt(select.value, 10);
          validateBtn.disabled = true;
          cancelBtn.disabled = true;

          try {
            const res = await fetch(`/users/${id}/branch`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              credentials: 'include',
              body: JSON.stringify({ branch_id: newBranch })
            });

            if (res.ok) {
              successDiv.textContent = 'Agence modifiée';
              successDiv.style.display = 'block';
              await loadUsers();
            } else {
              errorDiv.textContent = 'Erreur lors du changement d\'agence';
              errorDiv.style.display = 'block';
              td.innerHTML = originalHTML;
            }
          } catch (err) {
            errorDiv.textContent = 'Erreur réseau';
            errorDiv.style.display = 'block';
            td.innerHTML = originalHTML;
          }
        });

        cancelBtn.addEventListener('click', () => {
          td.innerHTML = originalHTML;
        });
      }
    } catch (err) {
      errorDiv.textContent = 'Erreur réseau';
      errorDiv.style.display = 'block';
      td.querySelectorAll('button').forEach(b => b.disabled = false);
    }
  }

  // Charge la liste des utilisateurs communs
  async function loadUsers() {
    try {
      const res = await fetch('/users/', { credentials: 'include' });
      if (!res.ok) throw new Error('Failed to load users');
      const users = await res.json();
      tableBody.innerHTML = '';

      if (users.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="3">Aucun utilisateur commun.</td></tr>';
        return;
      }

      users.forEach(u => {
        const row = document.createElement('tr');
        row.innerHTML = `
          <td>${u.username}</td>
          <td>${u.branch_id || '-'}</td>
          <td>
            <button data-id="${u.id}" class="btn-change-pwd">Changer mot de passe</button>
            <button data-id="${u.id}" class="btn-change-branch">Changer agence</button>
            <button data-id="${u.id}" class="btn-delete">Supprimer</button>
          </td>
        `;
        tableBody.appendChild(row);
      });
    } catch (e) {
      errorDiv.textContent = 'Erreur lors du chargement des utilisateurs';
      errorDiv.style.display = 'block';
    }
  }

  await loadUsers();

  // Formulaire de création d'utilisateur
  if (createForm) {
    createForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      errorDiv.style.display = 'none';
      successDiv.style.display = 'none';

      const username = document.getElementById('new-username').value.trim();
      const password = document.getElementById('new-password').value;
      const branchId = parseInt(document.getElementById('new-branch-id').value, 10);

      try {
        const res = await fetch('/users/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            username,
            password,
            branch_id: branchId
          })
        });
        if (!res.ok) throw new Error(await res.text());
        successDiv.textContent = 'Utilisateur créé avec succès';
        successDiv.style.display = 'block';
        createForm.reset();
        await loadUsers();
      } catch (err) {
        errorDiv.textContent = 'Erreur lors de la création';
        errorDiv.style.display = 'block';
      }
    });
  }
});
