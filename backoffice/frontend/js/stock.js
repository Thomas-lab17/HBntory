document.addEventListener('DOMContentLoaded', async () => {
  const STOCK_PAGE_SIZE = 8;
  const CATALOG_PAGE_SIZE = 9;
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
    stockPagination: document.getElementById('stock-pagination'),
    stockSearch: document.getElementById('stock-search'),
    categoryFilter: document.getElementById('stock-category-filter'),
    catalogSearch: document.getElementById('catalog-search'),
    catalogGrid: document.getElementById('catalog-grid'),
    catalogPagination: document.getElementById('catalog-pagination'),
    productDetailContent: document.getElementById('product-detail-content'),
    backToCatalog: document.getElementById('back-to-catalog'),
    productLoading: document.getElementById('product-loading'),
    productError: document.getElementById('product-error'),
    refreshProducts: document.getElementById('refresh-products'),
    dialog: document.getElementById('stock-dialog'),
    closeDialog: document.getElementById('close-stock-modal'),
    cancelDialog: document.getElementById('cancel-stock-modal'),
    deleteStockProduct: document.getElementById('delete-stock-product'),
    actionForm: document.getElementById('stock-action-form'),
    actionMode: document.getElementById('stock-action-mode'),
    actionProduct: document.getElementById('stock-product-id'),
    actionProductMonogram: document.getElementById('stock-product-monogram'),
    actionProductName: document.getElementById('stock-product-name'),
    actionProductMeta: document.getElementById('stock-product-meta'),
    actionProductCategory: document.getElementById('stock-product-category'),
    actionQuantity: document.getElementById('stock-quantity'),
    actionQuantityLabel: document.getElementById('stock-quantity-label'),
    actionQuantityHelp: document.getElementById('stock-quantity-help'),
    modalEyebrow: document.getElementById('modal-eyebrow'),
    modalTitle: document.getElementById('modal-title'),
    submitAction: document.getElementById('submit-stock-action'),
    breadcrumb: document.getElementById('breadcrumb-page'),
  };

  const state = {
    products: [],
    stocks: [],
    productsById: new Map(),
    productsLoaded: false,
    stockPage: 1,
    catalogPage: 1,
    detailReturnView: 'catalog-view',
    navigationKey: 'hbntory:navigation:guest',
  };

  function initials(value) {
    return value.trim().slice(0, 2).toUpperCase() || '—';
  }

  function loadLocalState() {
    try {
      const navigation = JSON.parse(localStorage.getItem(state.navigationKey) || '{}');
      return navigation;
    } catch {
      return {};
    }
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
    if (Array.isArray(data.detail)) {
      const message = data.detail
        .map((item) => item.msg?.replace(/^Value error, /, ''))
        .filter(Boolean)
        .join(' ');
      return new Error(message || fallback);
    }
    return new Error(data.detail || fallback);
  }

  function renderPagination(container, totalItems, currentPage, pageSize, onChange) {
    const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
    container.replaceChildren();
    if (totalItems <= pageSize) {
      container.hidden = true;
      return;
    }
    container.hidden = false;

    const firstItem = ((currentPage - 1) * pageSize) + 1;
    const lastItem = Math.min(currentPage * pageSize, totalItems);
    const label = document.createElement('span');
    label.className = 'pagination-summary';
    label.textContent = `${firstItem}–${lastItem} sur ${totalItems}`;

    const controls = document.createElement('div');
    controls.className = 'pagination-controls';

    const previous = document.createElement('button');
    previous.type = 'button';
    previous.className = 'pagination-button pagination-arrow';
    previous.setAttribute('aria-label', 'Page précédente');
    previous.textContent = '‹';
    previous.disabled = currentPage <= 1;
    previous.addEventListener('click', () => onChange(currentPage - 1));

    const pageNumbers = [];
    if (totalPages <= 7) {
      for (let page = 1; page <= totalPages; page += 1) pageNumbers.push(page);
    } else {
      pageNumbers.push(1);
      if (currentPage > 4) pageNumbers.push('start-ellipsis');
      const rangeStart = Math.max(2, currentPage - 1);
      const rangeEnd = Math.min(totalPages - 1, currentPage + 1);
      for (let page = rangeStart; page <= rangeEnd; page += 1) pageNumbers.push(page);
      if (currentPage < totalPages - 3) pageNumbers.push('end-ellipsis');
      pageNumbers.push(totalPages);
    }

    const next = document.createElement('button');
    next.type = 'button';
    next.className = 'pagination-button pagination-arrow';
    next.setAttribute('aria-label', 'Page suivante');
    next.textContent = '›';
    next.disabled = currentPage >= totalPages;
    next.addEventListener('click', () => onChange(currentPage + 1));

    controls.appendChild(previous);
    pageNumbers.forEach((page) => {
      if (typeof page !== 'number') {
        const ellipsis = document.createElement('span');
        ellipsis.className = 'pagination-ellipsis';
        ellipsis.textContent = '…';
        controls.appendChild(ellipsis);
        return;
      }

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'pagination-button';
      button.textContent = String(page);
      button.setAttribute('aria-label', `Page ${page}`);
      if (page === currentPage) {
        button.classList.add('is-current');
        button.setAttribute('aria-current', 'page');
      }
      button.addEventListener('click', () => onChange(page));
      controls.appendChild(button);
    });
    controls.appendChild(next);
    container.append(label, controls);
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

  function stockQuantityFor(productId) {
    const stock = state.stocks.find(
      (item) => String(item.external_product_id) === String(productId)
    );
    return stock?.quantity ?? 0;
  }

  function createStockStatus(quantity, compact = false) {
    const status = document.createElement('span');
    const level = quantity === 0 ? 'out' : quantity < 5 ? 'low' : 'available';
    status.className = `stock-status is-${level}${compact ? ' is-compact' : ''}`;
    status.textContent = quantity === 0 ? 'Rupture de stock' : `${quantity} UC`;
    return status;
  }

  function createOrderButton(productId) {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'btn btn-secondary btn-small btn-auto btn-order';
    button.dataset.stockAction = 'add';
    button.dataset.productId = productId;
    button.textContent = 'Commander';
    button.setAttribute('aria-label', 'Commander ce produit');
    return button;
  }

  function showView(viewId, breadcrumbLabel, productId = '') {
    document.querySelectorAll('.app-view').forEach((view) => {
      const isTarget = view.id === viewId;
      view.hidden = !isTarget;
      view.classList.toggle('is-active', isTarget);
    });
    document.querySelectorAll('[data-view-target]').forEach((item) => {
      const activeTarget = viewId === 'product-detail-view'
        ? state.detailReturnView
        : viewId;
      item.classList.toggle('is-active', item.dataset.viewTarget === activeTarget);
    });
    elements.breadcrumb.textContent = breadcrumbLabel;
    try {
      localStorage.setItem(
        state.navigationKey,
        JSON.stringify({
          view: viewId,
          productId: productId ? String(productId) : '',
          returnView: viewId === 'product-detail-view' ? state.detailReturnView : '',
        })
      );
    } catch {
      // La navigation fonctionne même si le stockage local est indisponible.
    }
  }

  function restoreNavigation(navigation) {
    if (navigation?.view === 'product-detail-view' && navigation.productId) {
      const product = state.productsById.get(String(navigation.productId));
      if (product) {
        openProductDetail(navigation.productId, navigation.returnView);
        return;
      }
    }
    if (navigation?.view === 'catalog-view') {
      showView('catalog-view', 'Catalogue');
    }
  }

  function formatCatalogDate(value) {
    if (!value) return 'Non renseignée';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return `${new Intl.DateTimeFormat('fr-FR', {
      dateStyle: 'long',
      timeStyle: 'short',
      timeZone: 'Europe/Paris',
    }).format(date)}`;
  }

  function createProductDetailItem(label, value) {
    const wrapper = document.createElement('div');
    wrapper.className = 'product-detail-item';
    const term = document.createElement('dt');
    term.textContent = label;
    const description = document.createElement('dd');
    if (value instanceof Node) {
      description.appendChild(value);
    } else {
      description.textContent = value === null || value === undefined || value === ''
        ? 'Non renseigné'
        : String(value);
    }
    wrapper.append(term, description);
    return wrapper;
  }

  function openProductDetail(productId, returnView = 'catalog-view') {
    const product = state.productsById.get(String(productId));
    if (!product) {
      showMessage(elements.error, 'Les informations de ce produit sont indisponibles.');
      return;
    }

    state.detailReturnView = returnView === 'stock-view' ? 'stock-view' : 'catalog-view';
    const backIcon = document.createElement('span');
    backIcon.setAttribute('aria-hidden', 'true');
    backIcon.textContent = '←';
    elements.backToCatalog.replaceChildren(
      backIcon,
      document.createTextNode(
        state.detailReturnView === 'stock-view'
          ? ' Retour au stock'
          : ' Retour au catalogue'
      )
    );

    const quantity = stockQuantityFor(product.id);
    const hero = document.createElement('article');
    hero.className = 'panel product-detail-hero';

    const heading = document.createElement('div');
    heading.className = 'product-detail-heading';
    const headingText = document.createElement('div');
    const eyebrow = document.createElement('span');
    eyebrow.className = 'eyebrow';
    eyebrow.textContent = product.category || 'Produit du catalogue';
    const title = document.createElement('h1');
    title.id = 'product-detail-title';
    title.textContent = product.name;
    const sku = document.createElement('p');
    sku.className = 'product-detail-sku';
    sku.textContent = product.sku;
    headingText.append(eyebrow, title, sku);

    const price = document.createElement('strong');
    price.className = 'product-detail-price';
    price.textContent = formatPrice(product) || 'Prix non renseigné';
    heading.append(headingText, price);

    const description = document.createElement('p');
    description.className = 'product-detail-description';
    description.textContent = product.description || 'Aucune description disponible.';

    const heroFooter = document.createElement('div');
    heroFooter.className = 'product-detail-hero-footer';
    heroFooter.appendChild(createStockStatus(quantity, true));
    const detailActions = document.createElement('div');
    detailActions.className = 'product-detail-actions';
    detailActions.appendChild(createOrderButton(product.id));
    heroFooter.appendChild(detailActions);
    hero.append(heading, description, heroFooter);

    const tags = document.createElement('div');
    tags.className = 'product-tag-list';
    if (Array.isArray(product.tags) && product.tags.length > 0) {
      product.tags.forEach((tag) => {
        const item = document.createElement('span');
        item.className = 'badge';
        item.textContent = tag;
        tags.appendChild(item);
      });
    } else {
      tags.textContent = 'Aucun tag';
    }

    const detailsPanel = document.createElement('section');
    detailsPanel.className = 'panel product-detail-panel';
    const detailsTitle = document.createElement('h2');
    detailsTitle.textContent = 'Toutes les informations';
    const details = document.createElement('dl');
    details.className = 'product-detail-grid';
    [
      ['Identifiant produit', product.id],
      ['SKU', product.sku],
      ['Catégorie', product.category],
      ['Marque', product.brand],
      ['Fournisseur', product.supplier_name],
      ['Identifiant fournisseur', product.supplier_id],
      ['Prix unitaire', formatPrice(product)],
      ['Devise', product.currency],
      ['Poids', product.weight_kg === null || product.weight_kg === undefined
        ? null
        : `${product.weight_kg} kg`],
      ['État catalogue', product.discontinued === true
        ? 'Arrêté'
        : product.discontinued === false
          ? 'Actif'
          : 'Non renseigné'],
      ['Dernière mise à jour', formatCatalogDate(product.updated_at)],
      ['Tags', tags],
    ].forEach(([label, value]) => {
      details.appendChild(createProductDetailItem(label, value));
    });
    detailsPanel.append(detailsTitle, details);

    elements.productDetailContent.replaceChildren(hero, detailsPanel);
    showView('product-detail-view', product.name, product.id);
    elements.backToCatalog.focus();
  }

  function productIdentity(product, fallbackId) {
    const wrapper = document.createElement('div');
    wrapper.className = 'cell-stack';

    const nameLine = document.createElement('div');
    nameLine.className = 'stock-product-name-line';
    const name = product
      ? document.createElement('button')
      : document.createElement('strong');
    name.textContent = product?.name || fallbackId;
    if (product) {
      name.type = 'button';
      name.className = 'stock-product-name-button';
      name.title = `Voir la fiche de ${product.name}`;
      name.addEventListener('click', () => openProductDetail(product.id, 'stock-view'));
    }
    nameLine.appendChild(name);

    wrapper.appendChild(nameLine);

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
      'Disponible (UC)',
      ...(showPrice ? ['Prix unitaire'] : []),
      'Actions',
    ].forEach((label, index, labels) => {
      const heading = document.createElement('th');
      heading.textContent = label;
      if (index === labels.length - 1) heading.className = 'align-right';
      headerRow.appendChild(heading);
    });
    elements.stockHead.replaceChildren(headerRow);

    const visibleStocks = state.stocks
      .filter(stockMatches)
      .sort((first, second) => {
        const firstIsOut = first.quantity === 0;
        const secondIsOut = second.quantity === 0;
        if (firstIsOut === secondIsOut) return 0;
        return firstIsOut ? -1 : 1;
      });
    const totalPages = Math.max(1, Math.ceil(visibleStocks.length / STOCK_PAGE_SIZE));
    state.stockPage = Math.min(state.stockPage, totalPages);
    const start = (state.stockPage - 1) * STOCK_PAGE_SIZE;
    const pageStocks = visibleStocks.slice(start, start + STOCK_PAGE_SIZE);
    elements.stockBody.replaceChildren();

    if (pageStocks.length === 0) {
      const row = document.createElement('tr');
      const cell = createCell(
        state.stocks.length === 0 ? 'Aucun produit en stock.' : 'Aucun résultat.',
        'empty-state'
      );
      cell.colSpan = headerRow.children.length;
      row.appendChild(cell);
      elements.stockBody.appendChild(row);
      elements.stockPagination.hidden = true;
      return;
    }

    pageStocks.forEach((item) => {
      const product = state.productsById.get(String(item.external_product_id));
      const row = document.createElement('tr');
      if (item.quantity === 0) {
        row.classList.add('is-out-of-stock');
      }
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

      row.appendChild(createCell(createStockStatus(item.quantity, true), 'quantity-cell'));
      if (showPrice) row.appendChild(createCell(formatPrice(product)));

      const actions = document.createElement('div');
      actions.className = 'table-actions';

      if (product) {
        const orderButton = createOrderButton(item.external_product_id);
        if (orderButton) actions.appendChild(orderButton);
      }

      const editButton = document.createElement('button');
      editButton.type = 'button';
      editButton.className = 'btn btn-secondary btn-small btn-auto';
      editButton.dataset.stockAction = 'update';
      editButton.dataset.productId = item.external_product_id;
      editButton.textContent = 'Modifier';
      actions.appendChild(editButton);

      row.appendChild(createCell(actions, 'align-right'));
      elements.stockBody.appendChild(row);
    });

    renderPagination(
      elements.stockPagination,
      visibleStocks.length,
      state.stockPage,
      STOCK_PAGE_SIZE,
      (page) => {
        state.stockPage = page;
        renderStock();
      }
    );
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
    const totalPages = Math.max(1, Math.ceil(products.length / CATALOG_PAGE_SIZE));
    state.catalogPage = Math.min(state.catalogPage, totalPages);
    const start = (state.catalogPage - 1) * CATALOG_PAGE_SIZE;
    const pageProducts = products.slice(start, start + CATALOG_PAGE_SIZE);

    if (pageProducts.length === 0) {
      const empty = document.createElement('div');
      empty.className = 'panel empty-state';
      empty.textContent = state.products.length === 0
        ? 'Aucun produit disponible dans l’API.'
        : elements.catalogSearch.value.trim()
          ? 'Aucun résultat.'
          : 'Aucun produit disponible dans l’API.';
      elements.catalogGrid.appendChild(empty);
      elements.catalogPagination.hidden = true;
      return;
    }

    pageProducts.forEach((product) => {
      const quantity = stockQuantityFor(product.id);
      const card = document.createElement('article');
      card.className = 'product-card';
      card.addEventListener('click', (event) => {
        if (event.target.closest('button, input, label, a')) return;
        openProductDetail(product.id);
      });

      const content = document.createElement('div');
      content.className = 'product-card-content';

      const header = document.createElement('div');
      header.className = 'product-card-header';
      const identity = document.createElement('div');
      identity.className = 'product-card-identity';
      const name = document.createElement('h3');
      const nameButton = document.createElement('button');
      nameButton.type = 'button';
      nameButton.className = 'product-name-button';
      nameButton.textContent = product.name;
      nameButton.title = `Voir toutes les informations de ${product.name}`;
      nameButton.addEventListener('click', () => openProductDetail(product.id));
      name.appendChild(nameButton);
      const sku = document.createElement('p');
      sku.className = 'sku';
      sku.textContent = product.sku;
      identity.append(name, sku);

      const identityGroup = document.createElement('div');
      identityGroup.className = 'product-card-title';
      identityGroup.appendChild(identity);
      header.appendChild(identityGroup);

      const price = formatPrice(product);
      if (price) {
        const priceElement = document.createElement('span');
        priceElement.className = 'product-price';
        priceElement.textContent = price;
        header.appendChild(priceElement);
      }

      const details = document.createElement('div');
      details.className = 'product-card-details';
      const metadata = document.createElement('div');
      metadata.className = 'product-metadata';
      if (product.category) {
        const category = document.createElement('span');
        category.className = 'badge';
        category.textContent = product.category;
        metadata.appendChild(category);
      }
      if (metadata.children.length > 0) details.appendChild(metadata);

      const footer = document.createElement('div');
      footer.className = 'product-card-footer';
      footer.appendChild(createStockStatus(quantity));
      footer.appendChild(createOrderButton(product.id));

      content.append(header, details, footer);
      card.appendChild(content);
      elements.catalogGrid.appendChild(card);
    });

    renderPagination(
      elements.catalogPagination,
      products.length,
      state.catalogPage,
      CATALOG_PAGE_SIZE,
      (page) => {
        state.catalogPage = page;
        renderCatalog();
      }
    );
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
    } catch (error) {
      state.products = [];
      state.productsById.clear();
      state.productsLoaded = false;
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
      renderCatalog();
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

  function populateActionProduct(selectedId) {
    const productId = String(selectedId || '');
    const product = state.productsById.get(productId);
    const quantity = stockQuantityFor(productId);

    elements.actionProduct.value = productId;
    elements.actionProductMonogram.textContent = (
      product?.category || product?.name || 'P'
    ).trim().charAt(0).toUpperCase();
    elements.actionProductName.textContent = product?.name || `Produit ${productId}`;
    elements.actionProductMeta.textContent = [
      product?.sku || productId,
      quantity === 0
        ? 'Rupture de stock'
        : `${quantity} UC en stock`,
    ].filter(Boolean).join(' • ');

    if (product?.category) {
      elements.actionProductCategory.textContent = product.category;
      elements.actionProductCategory.hidden = false;
    } else {
      elements.actionProductCategory.textContent = '';
      elements.actionProductCategory.hidden = true;
    }
  }

  function openStockDialog(mode, productId = '') {
    hideMessages();
    if (!productId) {
      showMessage(elements.error, 'Aucun produit n’a été sélectionné.');
      return;
    }

    elements.actionForm.reset();
    elements.actionMode.value = mode;
    const isOrder = mode === 'add';
    elements.modalEyebrow.textContent = isOrder
      ? 'Réapprovisionnement'
      : 'Modification du stock';
    elements.modalTitle.textContent = isOrder ? 'Commander ce produit' : 'Modifier la quantité';
    elements.actionQuantityLabel.textContent = isOrder
      ? 'Quantité à commander (UC)'
      : 'Nouvelle quantité en stock (UC)';
    elements.actionQuantityHelp.textContent = isOrder
      ? 'La quantité commandée sera ajoutée au stock actuel.'
      : 'Saisissez 0 pour passer le produit en rupture et activer sa suppression.';
    elements.submitAction.textContent = isOrder ? 'Confirmer la commande' : 'Enregistrer';
    elements.submitAction.className = 'btn btn-primary btn-auto';
    populateActionProduct(productId);
    elements.deleteStockProduct.hidden = isOrder;
    elements.deleteStockProduct.disabled = !isOrder && stockQuantityFor(productId) > 0;
    elements.deleteStockProduct.title = elements.deleteStockProduct.disabled
      ? 'Mettez d’abord la quantité à 0 et enregistrez la modification.'
      : 'Supprimer ce produit de la liste des stocks';
    elements.actionQuantity.min = isOrder ? '1' : '0';
    elements.actionQuantity.value = isOrder ? '1' : String(stockQuantityFor(productId));
    elements.dialog.showModal();
  }

  function closeStockDialog() {
    elements.dialog.close();
  }

  async function requestStockChange(mode, productId, quantity) {
    const response = await fetch(`/stock/${mode}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ external_product_id: productId, quantity }),
    });
    if (!response.ok) {
      throw await responseError(
        response,
        mode === 'add' ? 'Erreur lors de la commande.' : 'Erreur lors de la modification.'
      );
    }
    return response.json();
  }

  async function deleteStockRow(productId) {
    const response = await fetch(`/stock/${encodeURIComponent(productId)}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!response.ok) {
      throw await responseError(response, 'Erreur lors de la suppression du produit.');
    }
  }

  document.querySelectorAll('[data-view-target]').forEach((button) => {
    button.addEventListener('click', () => {
      showView(
        button.dataset.viewTarget,
        button.dataset.viewTarget === 'stock-view' ? 'Mon stock' : 'Catalogue'
      );
    });
  });

  elements.stockSearch.addEventListener('input', () => {
    state.stockPage = 1;
    renderStock();
  });
  elements.categoryFilter.addEventListener('change', () => {
    state.stockPage = 1;
    renderStock();
  });
  elements.catalogSearch.addEventListener('input', () => {
    state.catalogPage = 1;
    renderCatalog();
  });
  elements.closeDialog.addEventListener('click', closeStockDialog);
  elements.cancelDialog.addEventListener('click', closeStockDialog);
  elements.deleteStockProduct.addEventListener('click', async () => {
    const productId = elements.actionProduct.value;
    hideMessages();
    elements.deleteStockProduct.disabled = true;
    try {
      await deleteStockRow(productId);
      closeStockDialog();
      await loadStock();
      showMessage(elements.success, 'Produit supprimé de la liste des stocks.');
    } catch (error) {
      showMessage(elements.error, error.message);
      elements.deleteStockProduct.disabled = stockQuantityFor(productId) > 0;
    }
  });
  elements.backToCatalog.addEventListener('click', () => {
    const returnToStock = state.detailReturnView === 'stock-view';
    showView(
      returnToStock ? 'stock-view' : 'catalog-view',
      returnToStock ? 'Mon stock' : 'Catalogue'
    );
  });
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
    const minimum = mode === 'update' ? 0 : 1;
    if (!productId || !Number.isInteger(quantity) || quantity < minimum) {
      showMessage(
        elements.error,
        mode === 'update'
          ? 'La quantité doit être un nombre entier positif ou nul.'
          : 'Le produit et une quantité positive sont requis.'
      );
      return;
    }

    elements.submitAction.disabled = true;
    try {
      await requestStockChange(mode, productId, quantity);
      closeStockDialog();
      await loadStock();
      showMessage(
        elements.success,
        mode === 'add'
          ? 'Commande enregistrée et stock mis à jour.'
          : quantity === 0
            ? 'Stock mis à zéro. Le produit peut maintenant être supprimé.'
            : 'Quantité du stock mise à jour.'
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
    elements.userBranch.textContent = user.branch_name || '';
    elements.stockSubtitle.textContent = user.branch_name
      ? `Stock de l’agence ${user.branch_name}`
      : 'Stock de votre agence';

    const userScope = encodeURIComponent(`${user.username}:${user.branch_id || user.branch_name || 'default'}`);
    state.navigationKey = `hbntory:navigation:${userScope}`;
    const navigation = loadLocalState();
    await Promise.all([loadProducts(), loadStock()]);
    restoreNavigation(navigation);
  } catch {
    window.location.href = '/';
  }
});
