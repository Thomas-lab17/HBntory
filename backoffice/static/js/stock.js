document.addEventListener('DOMContentLoaded', async () => {
  const elements = {
    error: document.getElementById('error-message'),
    success: document.getElementById('success-message'),
    logout: document.getElementById('logout-btn'),
    userName: document.getElementById('user-name'),
    userInitials: document.getElementById('user-initials'),
    userBranch: document.getElementById('user-branch'),
    stockSubtitle: document.getElementById('stock-subtitle'),
    stockBody: document.getElementById('stock-table-body'),
    stockHead: document.getElementById('stock-table-head'),
    stockSearch: document.getElementById('stock-search'),
    categoryFilter: document.getElementById('stock-category-filter'),
    catalogSearch: document.getElementById('catalog-search'),
    catalogGrid: document.getElementById('catalog-grid'),
    productLoading: document.getElementById('product-loading'),
    productError: document.getElementById('product-error'),
    refreshProducts: document.getElementById('refresh-products'),
    openAddModal: document.getElementById('open-add-modal'),
    dialog: document.getElementById('stock-dialog'),
    closeDialog: document.getElementById('close-stock-modal'),
    cancelDialog: document.getElementById('cancel-stock-modal'),
    actionForm: document.getElementById('stock-action-form'),
    actionMode: document.getElementById('stock-action-mode'),
    actionProduct: document.getElementById('stock-product-id'),
    actionQuantity: document.getElementById('stock-quantity'),
    modalTitle: document.getElementById('modal-title'),
    submitAction: document.getElementById('submit-stock-action'),
    breadcrumb: document.getElementById('breadcrumb-page'),
  };

  const state = {
    products: [],
    stocks: [],
    productsById: new Map(),
    productsLoaded: false,
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
  }

  async function responseError(response, fallback) {
    const data = await response.json().catch(() => ({}));
    return new Error(data.detail || fallback);
  }

  function formatPrice(product) {
    if (product?.unit_price === null || product?.unit_price === undefined) return '';
    if (!product.currency) return String(product.unit_price);

    try {
      return new Intl.NumberFormat('fr-FR', {
        style: 'currency',
        currency: product.currency,
      }).format(product.unit_price);
    } catch {
      return `${product.unit_price} ${product.currency}`;
    }
  }

  function createCell(content, className = '') {
    const cell = document.createElement('td');
    if (className) cell.className = className;
    if (content instanceof Node) {
      cell.appendChild(content);
    } else {
      cell.textContent = content ?? '';
    }
    return cell;
  }

  function productIdentity(product, fallbackId) {
    const wrapper = document.createElement('div');
    wrapper.className = 'cell-stack';

    const name = document.createElement('strong');
    name.textContent = product?.name || fallbackId;
    wrapper.appendChild(name);

    if (product?.sku && product.sku !== product.name) {
      const sku = document.createElement('span');
      sku.textContent = product.sku;
      wrapper.appendChild(sku);
    }

    return wrapper;
  }

  function stockMatches(item) {
    const product = state.productsById.get(String(item.external_product_id));
    const query = elements.stockSearch.value.trim().toLocaleLowerCase('fr');
    const category = elements.categoryFilter.value;
    const haystack = [
      item.external_product_id,
      product?.name,
      product?.sku,
      product?.category,
    ].filter(Boolean).join(' ').toLocaleLowerCase('fr');

    return (!query || haystack.includes(query)) && (!category || product?.category === category);
  }

  function populateCategoryFilter() {
    const currentValue = elements.categoryFilter.value;
    const categories = [...new Set(
      state.stocks
        .map((item) => state.productsById.get(String(item.external_product_id))?.category)
        .filter(Boolean)
    )].sort((a, b) => a.localeCompare(b, 'fr'));

    elements.categoryFilter.replaceChildren();
    const allOption = document.createElement('option');
    allOption.value = '';
    allOption.textContent = 'Toutes les catégories';
    elements.categoryFilter.appendChild(allOption);

    categories.forEach((category) => {
      const option = document.createElement('option');
      option.value = category;
      option.textContent = category;
      elements.categoryFilter.appendChild(option);
    });

    elements.categoryFilter.hidden = categories.length === 0;
    if (categories.includes(currentValue)) elements.categoryFilter.value = currentValue;
  }

  function renderStock() {
    const showCategory = state.stocks.some((item) => {
      return Boolean(state.productsById.get(String(item.external_product_id))?.category);
    });
    const showPrice = state.stocks.some((item) => {
      const product = state.productsById.get(String(item.external_product_id));
      return product?.unit_price !== null && product?.unit_price !== undefined;
    });

    const headerRow = document.createElement('tr');
    [
      state.productsLoaded ? 'Produit / référence' : 'Identifiant produit',
      ...(showCategory ? ['Catégorie'] : []),
      'Disponible',
      ...(showPrice ? ['Prix unitaire'] : []),
      'Actions',
    ].forEach((label, index, labels) => {
      const heading = document.createElement('th');
      heading.textContent = label;
      if (index === labels.length - 1) heading.className = 'align-right';
      headerRow.appendChild(heading);
    });
    elements.stockHead.replaceChildren(headerRow);

    const visibleStocks = state.stocks.filter(stockMatches);
    elements.stockBody.replaceChildren();

    if (visibleStocks.length === 0) {
      const row = document.createElement('tr');
      const cell = createCell(
        state.stocks.length === 0 ? 'Aucun produit en stock.' : 'Aucun résultat.',
        'empty-state'
      );
      cell.colSpan = headerRow.children.length;
      row.appendChild(cell);
      elements.stockBody.appendChild(row);
      return;
    }

    visibleStocks.forEach((item) => {
      const product = state.productsById.get(String(item.external_product_id));
      const row = document.createElement('tr');
      const identityCell = createCell(productIdentity(product, item.external_product_id));
      identityCell.className = 'product-cell';
      row.appendChild(identityCell);

      if (showCategory) {
        const category = product?.category
          ? Object.assign(document.createElement('span'), {
              className: 'badge',
              textContent: product.category,
            })
          : '';
        row.appendChild(createCell(category));
      }

      row.appendChild(createCell(String(item.quantity), 'quantity'));
      if (showPrice) row.appendChild(createCell(formatPrice(product)));

      const actions = document.createElement('div');
      actions.className = 'table-actions';

      if (product) {
        const addButton = document.createElement('button');
        addButton.type = 'button';
        addButton.className = 'btn btn-primary btn-small btn-auto';
        addButton.dataset.stockAction = 'add';
        addButton.dataset.productId = item.external_product_id;
        addButton.textContent = '+ Ajouter';
        actions.appendChild(addButton);
      }

      const removeButton = document.createElement('button');
      removeButton.type = 'button';
      removeButton.className = 'btn btn-secondary btn-small btn-auto';
      removeButton.dataset.stockAction = 'remove';
      removeButton.dataset.productId = item.external_product_id;
      removeButton.textContent = 'Retirer';
      removeButton.disabled = item.quantity <= 0;
      actions.appendChild(removeButton);

      row.appendChild(createCell(actions, 'align-right'));
      elements.stockBody.appendChild(row);
    });
  }

  function catalogMatches(product) {
    const query = elements.catalogSearch.value.trim().toLocaleLowerCase('fr');
    if (!query) return true;
    return [product.name, product.sku, product.category]
      .filter(Boolean)
      .join(' ')
      .toLocaleLowerCase('fr')
      .includes(query);
  }

  function renderCatalog() {
    elements.catalogGrid.replaceChildren();
    const products = state.products.filter(catalogMatches);

    if (products.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'panel empty-state';
      empty.textContent = state.products.length === 0
        ? 'Aucun produit disponible.'
        : 'Aucun résultat.';
      elements.catalogGrid.appendChild(empty);
      return;
    }

    products.forEach((product) => {
      const card = document.createElement('article');
      card.className = 'product-card';

      const header = document.createElement('div');
      header.className = 'product-card-header';
      const identity = document.createElement('div');
      const name = document.createElement('h3');
      name.textContent = product.name;
      const sku = document.createElement('p');
      sku.className = 'sku';
      sku.textContent = product.sku;
      identity.append(name, sku);
      header.appendChild(identity);

      const price = formatPrice(product);
      if (price) {
        const priceElement = document.createElement('span');
        priceElement.className = 'product-price';
        priceElement.textContent = price;
        header.appendChild(priceElement);
      }

      const footer = document.createElement('div');
      footer.className = 'product-card-footer';
      if (product.category) {
        const category = document.createElement('span');
        category.className = 'badge';
        category.textContent = product.category;
        footer.appendChild(category);
      } else {
        footer.appendChild(document.createElement('span'));
      }

      const addButton = document.createElement('button');
      addButton.type = 'button';
      addButton.className = 'btn btn-primary btn-small btn-auto';
      addButton.dataset.stockAction = 'add';
      addButton.dataset.productId = product.id;
      addButton.textContent = '+ Ajouter au stock';
      footer.appendChild(addButton);

      card.append(header, footer);
      elements.catalogGrid.appendChild(card);
    });
  }

  async function loadProducts() {
    elements.productLoading.hidden = false;
    elements.productError.hidden = true;

    try {
      const response = await fetch('/products/', { credentials: 'include' });
      if (!response.ok) throw await responseError(response, 'Impossible de charger les produits.');

      state.products = await response.json();
      state.productsById = new Map(state.products.map((product) => [String(product.id), product]));
      state.productsLoaded = true;
      elements.openAddModal.disabled = state.products.length === 0;
    } catch (error) {
      state.products = [];
      state.productsById.clear();
      state.productsLoaded = false;
      elements.openAddModal.disabled = true;
      showMessage(elements.productError, error.message);
    } finally {
      elements.productLoading.hidden = true;
      populateCategoryFilter();
      renderStock();
      renderCatalog();
    }
  }

  async function loadStock() {
    try {
      const response = await fetch('/stock/', { credentials: 'include' });
      if (!response.ok) throw await responseError(response, 'Impossible de charger le stock.');
      state.stocks = await response.json();
      populateCategoryFilter();
      renderStock();
    } catch (error) {
      showMessage(elements.error, error.message);
      elements.stockBody.replaceChildren();
      const row = document.createElement('tr');
      const cell = createCell('Le stock est indisponible.', 'empty-state');
      cell.colSpan = 5;
      row.appendChild(cell);
      elements.stockBody.appendChild(row);
    }
  }

  function populateActionProducts(mode, selectedId = '') {
    elements.actionProduct.replaceChildren();
    const placeholder = document.createElement('option');
    placeholder.value = '';
    placeholder.textContent = 'Sélectionner un produit';
    elements.actionProduct.appendChild(placeholder);

    if (mode === 'add') {
      state.products.forEach((product) => {
        const option = document.createElement('option');
        option.value = product.id;
        option.textContent = `${product.name} (${product.sku})`;
        elements.actionProduct.appendChild(option);
      });
    } else {
      state.stocks.filter((item) => item.quantity > 0).forEach((item) => {
        const product = state.productsById.get(String(item.external_product_id));
        const option = document.createElement('option');
        option.value = item.external_product_id;
        option.textContent = product
          ? `${product.name} (${product.sku})`
          : item.external_product_id;
        elements.actionProduct.appendChild(option);
      });
    }

    if (selectedId) elements.actionProduct.value = String(selectedId);
  }

  function openStockDialog(mode, productId = '') {
    hideMessages();
    elements.actionForm.reset();
    elements.actionMode.value = mode;
    elements.modalTitle.textContent = mode === 'add' ? 'Ajouter du stock' : 'Retirer du stock';
    elements.submitAction.textContent = mode === 'add' ? 'Ajouter' : 'Retirer';
    elements.submitAction.className = mode === 'add'
      ? 'btn btn-primary btn-auto'
      : 'btn btn-danger btn-auto';
    populateActionProducts(mode, productId);
    elements.dialog.showModal();
  }

  function closeStockDialog() {
    elements.dialog.close();
  }

  document.querySelectorAll('[data-view-target]').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('[data-view-target]').forEach((item) => {
        item.classList.toggle('is-active', item === button);
      });
      document.querySelectorAll('.app-view').forEach((view) => {
        const isTarget = view.id === button.dataset.viewTarget;
        view.hidden = !isTarget;
        view.classList.toggle('is-active', isTarget);
      });
      elements.breadcrumb.textContent = button.dataset.viewTarget === 'stock-view'
        ? 'Stock'
        : 'Catalogue';
    });
  });

  elements.stockSearch.addEventListener('input', renderStock);
  elements.categoryFilter.addEventListener('change', renderStock);
  elements.catalogSearch.addEventListener('input', renderCatalog);
  elements.openAddModal.addEventListener('click', () => openStockDialog('add'));
  elements.closeDialog.addEventListener('click', closeStockDialog);
  elements.cancelDialog.addEventListener('click', closeStockDialog);
  elements.refreshProducts.addEventListener('click', loadProducts);

  document.addEventListener('click', (event) => {
    const button = event.target.closest('[data-stock-action]');
    if (!button) return;
    openStockDialog(button.dataset.stockAction, button.dataset.productId);
  });

  elements.actionForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    hideMessages();

    const mode = elements.actionMode.value;
    const productId = elements.actionProduct.value;
    const quantity = Number.parseInt(elements.actionQuantity.value, 10);
    if (!productId || !Number.isInteger(quantity) || quantity <= 0) {
      showMessage(elements.error, 'Sélectionnez un produit et une quantité positive.');
      return;
    }

    elements.submitAction.disabled = true;
    try {
      const response = await fetch(`/stock/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ external_product_id: productId, quantity }),
      });
      if (!response.ok) {
        throw await responseError(
          response,
          mode === 'add' ? 'Erreur lors de l’ajout.' : 'Erreur lors du retrait.'
        );
      }

      closeStockDialog();
      await loadStock();
      showMessage(
        elements.success,
        mode === 'add' ? 'Stock ajouté avec succès.' : 'Stock retiré avec succès.'
      );
    } catch (error) {
      closeStockDialog();
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
    if (user.role !== 'common') {
      window.location.href = '/users.html';
      return;
    }

    elements.userName.textContent = user.username;
    elements.userInitials.textContent = initials(user.username);
    elements.userBranch.textContent = user.branch_id ? `Agence #${user.branch_id}` : '';
    elements.stockSubtitle.textContent = user.branch_id
      ? `Stock de l’agence #${user.branch_id}`
      : 'Stock de votre agence';

    await Promise.all([loadProducts(), loadStock()]);
  } catch {
    window.location.href = '/';
  }
});
