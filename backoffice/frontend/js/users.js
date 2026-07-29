document.addEventListener('DOMContentLoaded', async () => {
  const PAGE_SIZE = 8;
  const elements = {
    userName: document.getElementById('user-name'),
    userInitials: document.getElementById('user-initials'),
    logout: document.getElementById('logout-btn'),
    error: document.getElementById('error-message'),
    success: document.getElementById('success-message'),
    breadcrumb: document.getElementById('admin-breadcrumb'),
    usersCount: document.getElementById('users-count'),
    usersSearch: document.getElementById('users-search'),
    usersBranchFilter: document.getElementById('users-branch-filter'),
    usersBody: document.getElementById('users-table-body'),
    usersPagination: document.getElementById('users-pagination'),
    branchesCount: document.getElementById('branches-count'),
    branchesSearch: document.getElementById('branches-search'),
    branchesBody: document.getElementById('branches-table-body'),
    branchesPagination: document.getElementById('branches-pagination'),
    createDialog: document.getElementById('create-user-dialog'),
    openCreate: document.getElementById('open-create-modal'),
    closeCreate: document.getElementById('close-create-modal'),
    cancelCreate: document.getElementById('cancel-create-modal'),
    createForm: document.getElementById('create-user-form'),
    newBranch: document.getElementById('new-branch-id'),
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
    branchDialog: document.getElementById('branch-dialog'),
    branchForm: document.getElementById('branch-form'),
    branchDialogTitle: document.getElementById('branch-dialog-title'),
    branchId: document.getElementById('branch-id'),
    branchName: document.getElementById('branch-name'),
    openBranch: document.getElementById('open-branch-modal'),
    closeBranch: document.getElementById('close-branch-modal'),
    cancelBranch: document.getElementById('cancel-branch-modal'),
  };

  const state = {
    users: [],
    branches: [],
    usersPage: 1,
    branchesPage: 1,
  };

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
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  async function responseError(response, fallback) {
    const data = await response.json().catch(() => ({}));
    if (Array.isArray(data.detail)) {
      const message = data.detail
        .map((item) => item.msg?.replace(/^Value error, /, ''))
        .filter(Boolean)
        .join(' ');
      return new Error(message || fallback);
    }
    return new Error(data.detail || fallback);
  }

  function createCell(content, className = '') {
    const cell = document.createElement('td');
    if (className) cell.className = className;
    if (content instanceof Node) cell.appendChild(content);
    else cell.textContent = content ?? '';
    return cell;
  }

  function actionButton(label, action, id, style = 'secondary') {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `btn btn-${style} btn-small btn-auto`;
    button.dataset.action = action;
    button.dataset.id = id;
    button.textContent = label;
    return button;
  }

  function renderPagination(container, totalItems, currentPage, onChange) {
    const totalPages = Math.max(1, Math.ceil(totalItems / PAGE_SIZE));
    container.replaceChildren();
    if (totalItems <= PAGE_SIZE) {
      container.hidden = true;
      return;
    }
    container.hidden = false;

    const label = document.createElement('span');
    label.textContent = `Page ${currentPage} sur ${totalPages}`;

    const controls = document.createElement('div');
    const previous = actionButton('Précédent', 'previous', 0);
    const next = actionButton('Suivant', 'next', 0);
    previous.disabled = currentPage <= 1;
    next.disabled = currentPage >= totalPages;
    previous.addEventListener('click', () => onChange(currentPage - 1));
    next.addEventListener('click', () => onChange(currentPage + 1));
    controls.append(previous, next);
    container.append(label, controls);
  }

  function filteredUsers() {
    const query = elements.usersSearch.value.trim().toLocaleLowerCase('fr');
    const branchId = elements.usersBranchFilter.value;
    return state.users.filter((user) => {
      const matchesQuery = !query || [
        user.username,
        user.role,
        user.branch_name,
      ].filter(Boolean).join(' ').toLocaleLowerCase('fr').includes(query);
      return matchesQuery && (!branchId || String(user.branch_id) === branchId);
    });
  }

  function renderUsers() {
    const users = filteredUsers();
    const totalPages = Math.max(1, Math.ceil(users.length / PAGE_SIZE));
    state.usersPage = Math.min(state.usersPage, totalPages);
    const start = (state.usersPage - 1) * PAGE_SIZE;
    const pageItems = users.slice(start, start + PAGE_SIZE);

    elements.usersBody.replaceChildren();
    elements.usersCount.textContent = users.length === state.users.length
      ? `${state.users.length} utilisateur${state.users.length > 1 ? 's' : ''}`
      : `${users.length} résultat${users.length > 1 ? 's' : ''} sur ${state.users.length}`;

    if (pageItems.length === 0) {
      const row = document.createElement('tr');
      const cell = createCell(
        state.users.length === 0 ? 'Aucun utilisateur.' : 'Aucun résultat.',
        'empty-state'
      );
      cell.colSpan = 4;
      row.appendChild(cell);
      elements.usersBody.appendChild(row);
    }

    pageItems.forEach((user) => {
      const row = document.createElement('tr');
      const userCell = document.createElement('div');
      userCell.className = 'user-cell';
      const avatar = document.createElement('span');
      avatar.className = 'avatar';
      avatar.textContent = initials(user.username);
      const username = document.createElement('strong');
      username.textContent = user.username;
      userCell.append(avatar, username);
      row.appendChild(createCell(userCell));

      const role = document.createElement('span');
      role.className = 'badge badge-primary';
      role.textContent = user.role === 'common' ? 'Utilisateur' : user.role;
      row.appendChild(createCell(role));
      row.appendChild(createCell(user.branch_name || 'Non affecté'));

      const actions = document.createElement('div');
      actions.className = 'table-actions';
      actions.append(
        actionButton('Mot de passe', 'password', user.id),
        actionButton('Agence', 'branch', user.id),
        actionButton('Supprimer', 'delete-user', user.id, 'danger')
      );
      row.appendChild(createCell(actions, 'align-right'));
      elements.usersBody.appendChild(row);
    });

    renderPagination(elements.usersPagination, users.length, state.usersPage, (page) => {
      state.usersPage = page;
      renderUsers();
    });
  }

  function filteredBranches() {
    const query = elements.branchesSearch.value.trim().toLocaleLowerCase('fr');
    return state.branches.filter((branch) => {
      return !query || branch.name.toLocaleLowerCase('fr').includes(query);
    });
  }

  function renderBranches() {
    const branches = filteredBranches();
    const totalPages = Math.max(1, Math.ceil(branches.length / PAGE_SIZE));
    state.branchesPage = Math.min(state.branchesPage, totalPages);
    const start = (state.branchesPage - 1) * PAGE_SIZE;
    const pageItems = branches.slice(start, start + PAGE_SIZE);

    elements.branchesBody.replaceChildren();
    elements.branchesCount.textContent = branches.length === state.branches.length
      ? `${state.branches.length} agence${state.branches.length > 1 ? 's' : ''}`
      : `${branches.length} résultat${branches.length > 1 ? 's' : ''} sur ${state.branches.length}`;

    if (pageItems.length === 0) {
      const row = document.createElement('tr');
      const cell = createCell(
        state.branches.length === 0 ? 'Aucune agence.' : 'Aucun résultat.',
        'empty-state'
      );
      cell.colSpan = 4;
      row.appendChild(cell);
      elements.branchesBody.appendChild(row);
    }

    pageItems.forEach((branch) => {
      const row = document.createElement('tr');
      const name = document.createElement('strong');
      name.textContent = branch.name;
      row.appendChild(createCell(name));
      row.appendChild(createCell(String(branch.user_count)));
      row.appendChild(createCell(String(branch.stock_count)));

      const actions = document.createElement('div');
      actions.className = 'table-actions';
      actions.append(
        actionButton('Renommer', 'edit-branch', branch.id),
        actionButton('Supprimer', 'delete-branch', branch.id, 'danger')
      );
      row.appendChild(createCell(actions, 'align-right'));
      elements.branchesBody.appendChild(row);
    });

    renderPagination(elements.branchesPagination, branches.length, state.branchesPage, (page) => {
      state.branchesPage = page;
      renderBranches();
    });
  }

  function populateBranchMenus() {
    [elements.newBranch, elements.actionBranch].forEach((select) => {
      const selected = select.value;
      select.replaceChildren();
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = 'Sélectionner une agence';
      select.appendChild(placeholder);
      state.branches.forEach((branch) => {
        const option = document.createElement('option');
        option.value = branch.id;
        option.textContent = branch.name;
        select.appendChild(option);
      });
      select.value = selected;
    });

    const selectedFilter = elements.usersBranchFilter.value;
    elements.usersBranchFilter.replaceChildren();
    const all = document.createElement('option');
    all.value = '';
    all.textContent = 'Toutes les agences';
    elements.usersBranchFilter.appendChild(all);
    state.branches.forEach((branch) => {
      const option = document.createElement('option');
      option.value = branch.id;
      option.textContent = branch.name;
      elements.usersBranchFilter.appendChild(option);
    });
    elements.usersBranchFilter.value = selectedFilter;
  }

  async function loadUsers() {
    const response = await fetch('/users/', { credentials: 'include' });
    if (!response.ok) throw await responseError(response, 'Impossible de charger les utilisateurs.');
    state.users = await response.json();
    renderUsers();
  }

  async function loadBranches() {
    const response = await fetch('/branches/', { credentials: 'include' });
    if (!response.ok) throw await responseError(response, 'Impossible de charger les agences.');
    state.branches = await response.json();
    populateBranchMenus();
    renderBranches();
  }

  async function reloadAll() {
    await loadBranches();
    await loadUsers();
  }

  function openUserAction(mode, userId) {
    const user = state.users.find((item) => String(item.id) === String(userId));
    if (!user) return;
    hideMessages();
    elements.actionForm.reset();
    elements.actionMode.value = mode;
    elements.actionUserId.value = userId;
    elements.actionEyebrow.textContent = user.username;
    elements.passwordField.hidden = mode !== 'password';
    elements.branchField.hidden = mode !== 'branch';
    elements.actionPassword.required = false;
    elements.actionBranch.required = mode === 'branch';
    setPasswordValidity(elements.actionPassword);
    elements.actionTitle.textContent = mode === 'password'
      ? 'Changer le mot de passe'
      : 'Changer l’agence';
    if (mode === 'branch') elements.actionBranch.value = user.branch_id || '';
    elements.actionDialog.showModal();
  }

  function openBranchDialog(branch = null) {
    hideMessages();
    elements.branchForm.reset();
    elements.branchId.value = branch?.id || '';
    elements.branchName.value = branch?.name || '';
    elements.branchDialogTitle.textContent = branch ? 'Renommer l’agence' : 'Nouvelle agence';
    elements.branchDialog.showModal();
    elements.branchName.focus();
  }

  async function deleteUser(userId) {
    const user = state.users.find((item) => String(item.id) === String(userId));
    if (!user || !window.confirm(`Supprimer l’utilisateur « ${user.username} » ?`)) return;
    hideMessages();
    const response = await fetch(`/users/${userId}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!response.ok) throw await responseError(response, 'Erreur lors de la suppression.');
    await reloadAll();
    showMessage(elements.success, 'Utilisateur supprimé.');
  }

  async function deleteBranch(branchId) {
    const branch = state.branches.find((item) => String(item.id) === String(branchId));
    if (!branch) return;
    hideMessages();
    const response = await fetch(`/branches/${branchId}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!response.ok) throw await responseError(response, 'Erreur lors de la suppression.');
    await reloadAll();
    showMessage(elements.success, 'Agence supprimée.');
  }

  document.querySelectorAll('[data-admin-view]').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('[data-admin-view]').forEach((item) => {
        item.classList.toggle('is-active', item === button);
      });
      document.querySelectorAll('.app-view').forEach((view) => {
        const active = view.id === button.dataset.adminView;
        view.hidden = !active;
        view.classList.toggle('is-active', active);
      });
      elements.breadcrumb.textContent = button.dataset.adminView === 'users-view'
        ? 'Utilisateurs'
        : 'Agences';
    });
  });

  elements.usersSearch.addEventListener('input', () => {
    state.usersPage = 1;
    renderUsers();
  });
  elements.usersBranchFilter.addEventListener('change', () => {
    state.usersPage = 1;
    renderUsers();
  });
  elements.branchesSearch.addEventListener('input', () => {
    state.branchesPage = 1;
    renderBranches();
  });

  elements.openCreate.addEventListener('click', () => {
    hideMessages();
    elements.createForm.reset();
    setPasswordValidity(document.getElementById('new-password'));
    elements.createDialog.showModal();
    document.getElementById('new-username').focus();
  });
  elements.closeCreate.addEventListener('click', () => elements.createDialog.close());
  elements.cancelCreate.addEventListener('click', () => elements.createDialog.close());
  elements.closeAction.addEventListener('click', () => elements.actionDialog.close());
  elements.cancelAction.addEventListener('click', () => elements.actionDialog.close());
  elements.openBranch.addEventListener('click', () => openBranchDialog());
  elements.closeBranch.addEventListener('click', () => elements.branchDialog.close());
  elements.cancelBranch.addEventListener('click', () => elements.branchDialog.close());

  document.querySelectorAll('[data-password-toggle]').forEach((button) => {
    button.addEventListener('click', () => {
      const input = document.getElementById(button.dataset.passwordToggle);
      const visible = input.type === 'text';
      input.type = visible ? 'password' : 'text';
      button.textContent = visible ? 'Afficher' : 'Masquer';
    });
  });

  function setPasswordValidity(input, reveal = false) {
    const value = input.value;
    const rules = {
      length: value.length >= 8,
      lower: /[a-z]/.test(value),
      upper: /[A-Z]/.test(value),
      number: /\d/.test(value),
      special: /[^A-Za-z0-9]/.test(value),
    };
    const valid = Object.values(rules).every(Boolean);

    const requirementsId = input.dataset.passwordRequirements;
    const requirements = requirementsId
      ? document.getElementById(requirementsId)
      : null;
    if (requirements) {
      requirements.querySelectorAll('[data-password-rule]').forEach((item) => {
        item.classList.toggle('is-valid', rules[item.dataset.passwordRule]);
      });
      const showRequirements = !valid && (Boolean(value) || reveal);
      requirements.classList.toggle('is-visible', showRequirements);
      requirements.setAttribute('aria-hidden', String(!showRequirements));
    }
    return valid;
  }
  ['new-password', 'action-password'].forEach((id) => {
    const input = document.getElementById(id);
    input.addEventListener('input', () => setPasswordValidity(input));
  });

  elements.usersBody.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    try {
      if (button.dataset.action === 'delete-user') await deleteUser(button.dataset.id);
      else openUserAction(button.dataset.action, button.dataset.id);
    } catch (error) {
      showMessage(elements.error, error.message);
    }
  });

  elements.branchesBody.addEventListener('click', async (event) => {
    const button = event.target.closest('[data-action]');
    if (!button) return;
    try {
      if (button.dataset.action === 'delete-branch') {
        await deleteBranch(button.dataset.id);
      } else {
        const branch = state.branches.find((item) => String(item.id) === button.dataset.id);
        if (branch) openBranchDialog(branch);
      }
    } catch (error) {
      showMessage(elements.error, error.message);
    }
  });

  elements.createForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    hideMessages();
    const password = document.getElementById('new-password');
    if (!setPasswordValidity(password, true)) {
      password.focus();
      return;
    }
    if (!elements.createForm.checkValidity()) {
      elements.createForm.querySelector(':invalid')?.focus();
      return;
    }

    const submit = elements.createForm.querySelector('button[type="submit"]');
    submit.disabled = true;
    try {
      const response = await fetch('/users/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          username: document.getElementById('new-username').value.trim(),
          password: password.value,
          branch_id: Number.parseInt(elements.newBranch.value, 10),
        }),
      });
      if (!response.ok) throw await responseError(response, 'Erreur lors de la création.');
      elements.createDialog.close();
      await reloadAll();
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
    if (
      mode === 'password'
      && !setPasswordValidity(elements.actionPassword, true)
    ) {
      elements.actionPassword.focus();
      return;
    }
    if (!elements.actionForm.checkValidity()) {
      elements.actionForm.querySelector(':invalid')?.focus();
      return;
    }

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
      await reloadAll();
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

  elements.branchForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    hideMessages();
    const branchId = elements.branchId.value;
    const response = await fetch(branchId ? `/branches/${branchId}` : '/branches/', {
      method: branchId ? 'PATCH' : 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ name: elements.branchName.value.trim() }),
    });
    if (!response.ok) {
      const error = await responseError(response, 'Impossible d’enregistrer l’agence.');
      elements.branchDialog.close();
      showMessage(elements.error, error.message);
      return;
    }
    elements.branchDialog.close();
    await reloadAll();
    showMessage(elements.success, branchId ? 'Agence renommée.' : 'Agence créée.');
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
    await reloadAll();
  } catch (error) {
    showMessage(elements.error, error.message || 'Le Backoffice est indisponible.');
  }
});
