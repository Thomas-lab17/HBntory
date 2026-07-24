document.addEventListener('DOMContentLoaded', async () => {
  const elements = {
    userName: document.getElementById('user-name'),
    userInitials: document.getElementById('user-initials'),
    logout: document.getElementById('logout-btn'),
    error: document.getElementById('error-message'),
    success: document.getElementById('success-message'),
    count: document.getElementById('users-count'),
    search: document.getElementById('users-search'),
    tableBody: document.getElementById('users-table-body'),
    createDialog: document.getElementById('create-user-dialog'),
    openCreate: document.getElementById('open-create-modal'),
    closeCreate: document.getElementById('close-create-modal'),
    cancelCreate: document.getElementById('cancel-create-modal'),
    createForm: document.getElementById('create-user-form'),
    actionDialog: document.getElementById('user-action-dialog'),
    actionForm: document.getElementById('user-action-form'),
    actionTitle: document.getElementById('user-action-title'),
    actionEyebrow: document.getElementById('user-action-eyebrow'),
    actionUserId: document.getElementById('action-user-id'),
    actionMode: document.getElementById('action-user-mode'),
    passwordField: document.getElementById('password-action-field'),
    branchField: document.getElementById('branch-action-field'),
    actionPassword: document.getElementById('action-password'),
    actionBranch: document.getElementById('action-branch-id'),
    submitAction: document.getElementById('submit-user-action'),
    closeAction: document.getElementById('close-user-action-modal'),
    cancelAction: document.getElementById('cancel-user-action-modal'),
  };

  const state = { users: [] };

  function initials(value) {
    return value.trim().slice(0, 2).toUpperCase() || '—';
  }

  function hideMessages() {
    elements.error.hidden = true;
    elements.success.hidden = true;
  }

  function showMessage(element, message) {
    element.textContent = message;
    element.hidden = false;
  }

  async function responseError(response, fallback) {
    const data = await response.json().catch(() => ({}));
    return new Error(data.detail || fallback);
  }

  function createCell(content, className = '') {
    const cell = document.createElement('td');
    if (className) cell.className = className;
    if (content instanceof Node) cell.appendChild(content);
    else cell.textContent = content ?? '';
    return cell;
  }

  function visibleUsers() {
    const query = elements.search.value.trim().toLocaleLowerCase('fr');
    if (!query) return state.users;
    return state.users.filter((user) => {
      return [user.username, user.role, user.branch_id]
        .filter((value) => value !== null && value !== undefined)
        .join(' ')
        .toLocaleLowerCase('fr')
        .includes(query);
    });
  }

  function actionButton(label, action, id, style = 'secondary') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `btn btn-${style} btn-small btn-auto`;
    button.dataset.userAction = action;
    button.dataset.userId = id;
    button.textContent = label;
    return button;
  }

  function renderUsers() {
    const users = visibleUsers();
    elements.tableBody.replaceChildren();
    elements.count.textContent = `${state.users.length} utilisateur${state.users.length > 1 ? 's' : ''}`;

    if (users.length === 0) {
      const row = document.createElement('tr');
      const cell = createCell(
        state.users.length === 0 ? 'Aucun utilisateur commun.' : 'Aucun résultat.',
        'empty-state'
      );
      cell.colSpan = 4;
      row.appendChild(cell);
      elements.tableBody.appendChild(row);
      return;
    }

    users.forEach((user) => {
      const row = document.createElement('tr');

      const userCell = document.createElement('div');
      userCell.className = 'user-cell';
      const avatar = document.createElement('span');
      avatar.className = 'avatar';
      avatar.textContent = initials(user.username);
      const identity = document.createElement('div');
      identity.className = 'cell-stack';
      const username = document.createElement('strong');
      username.textContent = user.username;
      identity.appendChild(username);
      userCell.append(avatar, identity);
      row.appendChild(createCell(userCell));

      const role = document.createElement('span');
      role.className = 'badge badge-primary';
      role.textContent = user.role;
      row.appendChild(createCell(role));
      row.appendChild(createCell(user.branch_id ? `#${user.branch_id}` : '—'));

      const actions = document.createElement('div');
      actions.className = 'table-actions';
      actions.append(
        actionButton('Mot de passe', 'password', user.id),
        actionButton('Agence', 'branch', user.id),
        actionButton('Supprimer', 'delete', user.id, 'danger')
      );
      row.appendChild(createCell(actions, 'align-right'));

      elements.tableBody.appendChild(row);
    });
  }

  async function loadUsers() {
    try {
      const response = await fetch('/users/', { credentials: 'include' });
      if (!response.ok) throw await responseError(response, 'Impossible de charger les utilisateurs.');
      state.users = await response.json();
      renderUsers();
    } catch (error) {
      showMessage(elements.error, error.message);
      state.users = [];
      renderUsers();
    }
  }

  function openActionDialog(mode, userId) {
    const user = state.users.find((item) => String(item.id) === String(userId));
    if (!user) return;

    hideMessages();
    elements.actionForm.reset();
    elements.actionMode.value = mode;
    elements.actionUserId.value = userId;
    elements.actionEyebrow.textContent = user.username;
    elements.passwordField.hidden = mode !== 'password';
    elements.branchField.hidden = mode !== 'branch';
    elements.actionPassword.required = mode === 'password';
    elements.actionBranch.required = mode === 'branch';

    if (mode === 'password') {
      elements.actionTitle.textContent = 'Changer le mot de passe';
      elements.submitAction.textContent = 'Mettre à jour';
    } else {
      elements.actionTitle.textContent = 'Changer l’agence';
      elements.submitAction.textContent = 'Mettre à jour';
      elements.actionBranch.value = user.branch_id || '';
    }

    elements.actionDialog.showModal();
  }

  async function deleteUser(userId) {
    const user = state.users.find((item) => String(item.id) === String(userId));
    if (!user || !window.confirm(`Supprimer l’utilisateur « ${user.username} » ?`)) return;

    hideMessages();
    try {
      const response = await fetch(`/users/${userId}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (!response.ok) throw await responseError(response, 'Erreur lors de la suppression.');
      await loadUsers();
      showMessage(elements.success, 'Utilisateur supprimé.');
    } catch (error) {
      showMessage(elements.error, error.message);
    }
  }

  elements.search.addEventListener('input', renderUsers);
  elements.openCreate.addEventListener('click', () => {
    hideMessages();
    elements.createForm.reset();
    elements.createDialog.showModal();
  });
  elements.closeCreate.addEventListener('click', () => elements.createDialog.close());
  elements.cancelCreate.addEventListener('click', () => elements.createDialog.close());
  elements.closeAction.addEventListener('click', () => elements.actionDialog.close());
  elements.cancelAction.addEventListener('click', () => elements.actionDialog.close());

  elements.tableBody.addEventListener('click', (event) => {
    const button = event.target.closest('[data-user-action]');
    if (!button) return;
    if (button.dataset.userAction === 'delete') {
      deleteUser(button.dataset.userId);
    } else {
      openActionDialog(button.dataset.userAction, button.dataset.userId);
    }
  });

  elements.createForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    hideMessages();

    const submit = elements.createForm.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      const response = await fetch('/users/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          username: document.getElementById('new-username').value.trim(),
          password: document.getElementById('new-password').value,
          branch_id: Number.parseInt(document.getElementById('new-branch-id').value, 10),
        }),
      });
      if (!response.ok) throw await responseError(response, 'Erreur lors de la création.');

      elements.createDialog.close();
      await loadUsers();
      showMessage(elements.success, 'Utilisateur créé avec succès.');
    } catch (error) {
      elements.createDialog.close();
      showMessage(elements.error, error.message);
    } finally {
      submit.disabled = false;
    }
  });

  elements.actionForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    hideMessages();

    const mode = elements.actionMode.value;
    const userId = elements.actionUserId.value;
    const endpoint = mode === 'password' ? 'password' : 'branch';
    const payload = mode === 'password'
      ? { new_password: elements.actionPassword.value }
      : { branch_id: Number.parseInt(elements.actionBranch.value, 10) };

    elements.submitAction.disabled = true;
    try {
      const response = await fetch(`/users/${userId}/${endpoint}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(payload),
      });
      if (!response.ok) throw await responseError(response, 'Erreur lors de la modification.');

      elements.actionDialog.close();
      await loadUsers();
      showMessage(
        elements.success,
        mode === 'password' ? 'Mot de passe modifié.' : 'Agence modifiée.'
      );
    } catch (error) {
      elements.actionDialog.close();
      showMessage(elements.error, error.message);
    } finally {
      elements.submitAction.disabled = false;
    }
  });

  elements.logout.addEventListener('click', async () => {
    await fetch('/auth/logout', { method: 'POST', credentials: 'include' });
    window.location.href = '/';
  });

  try {
    const response = await fetch('/auth/me', { credentials: 'include' });
    if (!response.ok) {
      window.location.href = '/';
      return;
    }

    const user = await response.json();
    if (user.role !== 'admin') {
      window.location.href = '/stock.html';
      return;
    }

    elements.userName.textContent = user.username;
    elements.userInitials.textContent = initials(user.username);
    await loadUsers();
  } catch {
    window.location.href = '/';
  }
});
