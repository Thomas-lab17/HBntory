document.addEventListener('DOMContentLoaded', async () => {
  const userInfo = document.getElementById('user-info');
  const stockTitle = document.getElementById('stock-title');
  const errorDiv = document.getElementById('error-message');
  const successDiv = document.getElementById('success-message');
  const logoutBtn = document.getElementById('logout-btn');
  const tableBody = document.getElementById('stock-table-body');
  const addForm = document.getElementById('add-form');
  const removeForm = document.getElementById('remove-form');
  const loadingDiv = document.getElementById('product-loading');
  const productErrorDiv = document.getElementById('product-error');
  const addSelect = document.getElementById('add-product-id');
  const removeSelect = document.getElementById('remove-product-id');

  let addTomSelect = null;
  let removeTomSelect = null;

  // Check authentication
  try {
    const res = await fetch('/auth/me', { credentials: 'include' });
    if (!res.ok) {
      window.location.href = 'index.html';
      return;
    }
    const user = await res.json();
    if (user.role !== 'common') {
      window.location.href = 'index.html';
      return;
    }
    userInfo.textContent = `Connecté en tant que ${user.username} – Agence ${user.branch_id || '-'}`;
    stockTitle.textContent = `Stock – Agence ${user.branch_id || '-'}`;
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

  async function loadStock() {
    try {
      const res = await fetch('/stock/', { credentials: 'include' });
      if (!res.ok) throw new Error('Failed to load stock');
      const stocks = await res.json();
      tableBody.innerHTML = '';
      if (stocks.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="3">Aucun produit en stock.</td></tr>';
        return;
      }
      stocks.forEach(item => {
        const row = document.createElement('tr');
        row.innerHTML = `
          <td>${item.external_product_id}</td>
          <td>${item.quantity}</td>
          <td>—</td>
        `;
        tableBody.appendChild(row);
      });
    } catch (e) {
      errorDiv.textContent = 'Erreur lors du chargement du stock';
      errorDiv.style.display = 'block';
    }
  }

  await loadStock();

  // Load products and initialize Tom Select
  async function initProductSelectors() {
    loadingDiv.style.display = 'block';
    productErrorDiv.style.display = 'none';

    try {
      const res = await fetch('/products/', { credentials: 'include' });
      if (!res.ok) throw new Error('Failed to load products');

      const products = await res.json();

      if (!products || products.length === 0) {
        loadingDiv.style.display = 'none';
        productErrorDiv.style.display = 'block';
        addSelect.disabled = true;
        removeSelect.disabled = true;
        return;
      }

      // Populate selects
      addSelect.innerHTML = '<option value="">Sélectionner un produit</option>';
      removeSelect.innerHTML = '<option value="">Sélectionner un produit</option>';

      products.forEach(p => {
        const optionAdd = document.createElement('option');
        optionAdd.value = p.id;
        optionAdd.textContent = p.name;
        addSelect.appendChild(optionAdd);

        const optionRemove = document.createElement('option');
        optionRemove.value = p.id;
        optionRemove.textContent = p.name;
        removeSelect.appendChild(optionRemove);
      });

      // Initialize Tom Select
      addTomSelect = new TomSelect(addSelect, {
        create: false,
        sortField: { field: 'text', direction: 'asc' }
      });

      removeTomSelect = new TomSelect(removeSelect, {
        create: false,
        sortField: { field: 'text', direction: 'asc' }
      });

    } catch (e) {
      loadingDiv.style.display = 'none';
      productErrorDiv.style.display = 'block';
      addSelect.disabled = true;
      removeSelect.disabled = true;
    } finally {
      loadingDiv.style.display = 'none';
    }
  }

  await initProductSelectors();

  // Add stock form
  if (addForm) {
    addForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      errorDiv.style.display = 'none';
      successDiv.style.display = 'none';

      const productId = addTomSelect ? addTomSelect.getValue() : '';
      const qty = parseInt(document.getElementById('add-quantity').value, 10);

      if (!productId) {
        errorDiv.textContent = 'Veuillez sélectionner un produit';
        errorDiv.style.display = 'block';
        return;
      }

      try {
        const res = await fetch('/stock/add', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ external_product_id: productId, quantity: qty })
        });
        if (!res.ok) throw new Error(await res.text());
        successDiv.textContent = 'Stock ajouté avec succès';
        successDiv.style.display = 'block';
        addForm.reset();
        if (addTomSelect) addTomSelect.clear();
        await loadStock();
      } catch (err) {
        errorDiv.textContent = 'Erreur lors de l\'ajout';
        errorDiv.style.display = 'block';
      }
    });
  }

  // Remove stock form
  if (removeForm) {
    removeForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      errorDiv.style.display = 'none';
      successDiv.style.display = 'none';

      const productId = removeTomSelect ? removeTomSelect.getValue() : '';
      const qty = parseInt(document.getElementById('remove-quantity').value, 10);

      if (!productId) {
        errorDiv.textContent = 'Veuillez sélectionner un produit';
        errorDiv.style.display = 'block';
        return;
      }

      try {
        const res = await fetch('/stock/remove', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({ external_product_id: productId, quantity: qty })
        });
        if (!res.ok) throw new Error(await res.text());
        successDiv.textContent = 'Stock retiré avec succès';
        successDiv.style.display = 'block';
        removeForm.reset();
        if (removeTomSelect) removeTomSelect.clear();
        await loadStock();
      } catch (err) {
        errorDiv.textContent = 'Erreur lors du retrait';
        errorDiv.style.display = 'block';
      }
    });
  }
});
