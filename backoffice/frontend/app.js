/* Frontend HBntory
   Principe : un token JWT est stocké dans localStorage
   ("hbntory_token") et envoyé dans l'en-tête Authorization de chaque
   requête API. La vue affichée dépend du rôle renvoyé par /api/login :
   - "common" -> section stock (limitée à sa branche côté serveur)
   - "admin"  -> section gestion des utilisateurs */

const loginView = document.getElementById("login-view");
const appView = document.getElementById("app-view");
const loginForm = document.getElementById("login-form");
const loginError = document.getElementById("login-error");
const userBadge = document.getElementById("user-badge");
const logoutBtn = document.getElementById("logout-btn");
const flash = document.getElementById("flash");

const stockSection = document.getElementById("stock-section");
const stockBody = document.getElementById("stock-body");
const stockEmpty = document.getElementById("stock-empty");
const addForm = document.getElementById("add-form");
const removeForm = document.getElementById("remove-form");

const usersSection = document.getElementById("users-section");
const usersBody = document.getElementById("users-body");
const createUserForm = document.getElementById("create-user-form");
const editUserForm = document.getElementById("edit-user-form");
const editCancelBtn = document.getElementById("edit-cancel");

// Ces valeurs sont conservées pendant la session et servent à choisir la vue.
let me = null;
let branches = [];
let token = localStorage.getItem("hbntory_token") || null;

// Toutes les requêtes passent ici afin d'ajouter le token et de centraliser
// la gestion des erreurs renvoyées par l'API.
/* Appelle l'API en injectant le token Bearer ; lève une Error avec le
   message français renvoyé par le serveur en cas d'échec. */
async function api(path, options = {}) {
  const headers = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(path, { ...options, headers });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.error || `Échec de la requête (${res.status})`);
  }
  return data;
}

// Affiche les retours d'action dans le bandeau commun aux deux vues.
function showFlash(message, isError = false) {
  flash.textContent = message;
  flash.classList.toggle("error", isError);
  flash.classList.remove("hidden");
}
// Libellé lisible du rôle (le rôle brut "admin"/"common" prête à confusion
// avec les mots de passe de démonstration, qui leur sont identiques).
function roleLabel(role) {
  return role === "admin" ? "Administrateur" : "Utilisateur";
}

// Une déconnexion supprime aussi le token local pour éviter sa réutilisation.
function showLogin() {
  me = null;
  token = null;
  localStorage.removeItem("hbntory_token");
  appView.classList.add("hidden");
  loginView.classList.remove("hidden");
  loginError.classList.add("hidden");
  loginForm.reset();
}

// Une seule vue est visible selon le rôle renvoyé par le serveur.
async function showApp() {
  loginView.classList.add("hidden");
  appView.classList.remove("hidden");
  userBadge.textContent = `${me.username} · ${roleLabel(me.role)}` +
    (me.branch_name ? ` · ${me.branch_name}` : "");
  flash.classList.add("hidden");

  const isCommon = me.role === "common";
  const isAdmin = me.role === "admin";
  stockSection.classList.toggle("hidden", !isCommon);
  usersSection.classList.toggle("hidden", !isAdmin);

  if (isCommon) {
    document.getElementById("stock-title").textContent =
      `Stock — ${me.branch_name}`;
    await refreshStock();
  }
  if (isAdmin) {
    await refreshUsers();
  }
}

// ---- Stock de la branche de l'utilisateur connecté ----
async function refreshStock() {
  const data = await api("/api/stock");
  stockBody.innerHTML = "";
  stockEmpty.classList.toggle(
    "hidden",
    data.stock.length > 0
  );
  for (const item of data.stock) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${item.product_id}</td><td>${item.quantity}</td>`;
    stockBody.appendChild(tr);
  }
}

// Le serveur fusionne automatiquement deux ajouts pour un même produit.
addForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(addForm);
  try {
    const data = await api("/api/stock/add", {
      method: "POST",
      body: JSON.stringify({
        product_id: Number(fd.get("product_id")),
        quantity: Number(fd.get("quantity")),
      }),
    });
    addForm.reset();
    showFlash(`Stock ajouté : le produit ${data.stock.product_id} passe à ${data.stock.quantity} unité(s).`);
    await refreshStock();
  } catch (err) {
    showFlash(err.message, true);
  }
});

// Le serveur refuse le retrait si la quantité demandée dépasse le stock.
removeForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(removeForm);
  try {
    const data = await api("/api/stock/remove", {
      method: "POST",
      body: JSON.stringify({
        product_id: Number(fd.get("product_id")),
        quantity: Number(fd.get("quantity")),
      }),
    });
    removeForm.reset();
    showFlash(`Stock retiré : le produit ${data.stock.product_id} passe à ${data.stock.quantity} unité(s).`);
    await refreshStock();
  } catch (err) {
    showFlash(err.message, true);
  }
});

// ---- Gestion des utilisateurs, réservée à l'administrateur ----
function fillBranchSelect(select, selectedId, withEmpty) {
  select.innerHTML = "";
  if (withEmpty) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "—";
    select.appendChild(opt);
  }
  for (const b of branches) {
    const opt = document.createElement("option");
    opt.value = b.id;
    opt.textContent = b.name;
    if (b.id === selectedId) opt.selected = true;
    select.appendChild(opt);
  }
}

// Les branches sont chargées avant la liste des utilisateurs pour alimenter
// les formulaires de création et de modification.
async function loadBranches() {
  const data = await api("/api/branches");
  branches = data.branches;
  fillBranchSelect(createUserForm.elements.branch_id, null, false);
}

// Reconstruit le tableau afin d'afficher immédiatement chaque modification.
async function refreshUsers() {
  await loadBranches();
  const data = await api("/api/users");
  usersBody.innerHTML = "";
  editUserForm.classList.add("hidden");
  for (const u of data.users) {
    const tr = document.createElement("tr");

    // Badge de statut : admin / actif / supprimé.
    const statusBadge = u.role === "admin"
      ? '<span class="badge active">administrateur</span>'
      : u.is_deleted
        ? '<span class="badge deleted">supprimé</span>'
        : '<span class="badge active">actif</span>';

    // Pas de boutons sur l'admin ni sur un compte déjà supprimé.
    let actions = "";
    if (u.role !== "admin" && !u.is_deleted) {
      actions = `
        <button class="btn-ghost btn-small" data-edit="${u.id}">Modifier</button>
        <button class="btn-danger btn-small" data-delete="${u.id}">Supprimer</button>`;
    }

    tr.innerHTML = `
      <td>${u.id}</td>
      <td>${u.username}</td>
      <td>${u.branch_name ?? "—"}</td>
      <td>${statusBadge}</td>
      <td><div class="actions">${actions}</div></td>`;

    // Branche les boutons de la ligne aux actions correspondantes.
    const editBtn = tr.querySelector("[data-edit]");
    if (editBtn) {
      editBtn.addEventListener("click", () => startEdit(u));
    }
    const deleteBtn = tr.querySelector("[data-delete]");
    if (deleteBtn) {
      deleteBtn.addEventListener("click", () => deleteUser(u));
    }
    usersBody.appendChild(tr);
  }
}

// Le mot de passe est volontairement laissé vide quand on ouvre une édition.
function startEdit(u) {
  editUserForm.dataset.userId = u.id;
  document.getElementById("edit-user-id").textContent = u.id;
  editUserForm.elements.username.value = u.username;
  editUserForm.elements.password.value = "";
  fillBranchSelect(editUserForm.elements.branch_id, u.branch_id, false);
  editUserForm.classList.remove("hidden");
}

editCancelBtn.addEventListener("click", () => {
  editUserForm.classList.add("hidden");
});

// Un mot de passe vide n'est pas envoyé : l'ancien reste inchangé.
editUserForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {};
  body.username = editUserForm.elements.username.value.trim();
  const password = editUserForm.elements.password.value;
  if (password) body.password = password;
  body.branch_id = Number(editUserForm.elements.branch_id.value);
  try {
    await api(`/api/users/${editUserForm.dataset.userId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    editUserForm.reset();
    showFlash("Utilisateur mis à jour.");
    await refreshUsers();
  } catch (err) {
    showFlash(err.message, true);
  }
});

// L'API impose le rôle "common" pour tout nouvel utilisateur.
createUserForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(createUserForm);
  try {
    const data = await api("/api/users", {
      method: "POST",
      body: JSON.stringify({
        username: fd.get("username"),
        password: fd.get("password"),
        branch_id: Number(fd.get("branch_id")),
      }),
    });
    createUserForm.reset();
    showFlash(`Utilisateur « ${data.user.username} » créé.`);
    await refreshUsers();
  } catch (err) {
    showFlash(err.message, true);
  }
});

// La suppression est douce : le compte disparaît de l'accès mais reste connu
// du serveur pour invalider ses tokens existants.
async function deleteUser(u) {
  if (!confirm(`Supprimer l'utilisateur « ${u.username} » ?`)) return;
  try {
    await api(`/api/users/${u.id}`, { method: "DELETE" });
    showFlash(`Utilisateur « ${u.username} » supprimé.`);
    await refreshUsers();
  } catch (err) {
    showFlash(err.message, true);
  }
}

// ---- Connexion et restauration d'une session existante ----
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(loginForm);
  try {
    const data = await api("/api/login", {
      method: "POST",
      body: JSON.stringify({
        username: fd.get("username"),
        password: fd.get("password"),
      }),
    });
    token = data.token;
    localStorage.setItem("hbntory_token", token);
    me = data.user;
    loginForm.reset();
    await showApp();
  } catch (err) {
    // Identifiants invalides : message rouge sous le formulaire.
    loginError.textContent = err.message;
    loginError.classList.remove("hidden");
  }
});

logoutBtn.addEventListener("click", () => {
  showLogin();
});

/* Au chargement : un token existant est revalidé via /api/me ;
  sinon (ou s'il est expiré) on affiche l'écran de connexion. */
(async function init() {
  if (!token) {
    showLogin();
    return;
  }
  try {
    const data = await api("/api/me");
    if (data.user) {
      me = data.user;
      await showApp();
    } else {
      showLogin();
    }
  } catch {
    showLogin();
  }
})();
