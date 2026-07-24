# Sécurité web : XSS, CSRF, cookies et JWT

Ce document explique le modèle d'authentification du backoffice HBntory, les
risques XSS et CSRF qui y sont associés, et la cible recommandée pour un projet
à exigences de sécurité élevées.

> Ce document décrit l'état du code au 24 juillet 2026. Il ne remplace pas une
> revue de sécurité, des tests d'intrusion ou l'analyse des contraintes légales
> applicables (par exemple RGPD).

## Résumé

| Sujet | Application actuelle | Projet à sécurité élevée |
|---|---|---|
| Authentification | JWT HS256 dans un cookie | Session opaque côté serveur, ou JWT court + refresh token rotatif |
| Lecture du token par JavaScript | Non (`HttpOnly`) | Non (`HttpOnly`) |
| Protection CSRF | `SameSite=Lax` seulement | Jeton CSRF contrôlé côté serveur + vérification `Origin`/`Referer` |
| Révocation | Suppression du cookie côté navigateur | Révocation serveur, rotation et détection de réutilisation |
| Secret JWT | Variable d'environnement, mais valeur de secours de développement | Secret obligatoire, stocké dans un gestionnaire de secrets, rotation planifiée |
| Défense XSS | Bonne base : rendu avec `textContent` observé dans le front | CSP stricte avec nonce, validation/sanitation, contrôle des dépendances |

## 1. Les notions essentielles

### JWT

Un JSON Web Token (JWT) est une chaîne signée, composée de trois parties :

```text
base64url(header).base64url(payload).base64url(signature)
```

La signature prouve qu'il a été émis par le serveur et qu'il n'a pas été
modifié. Elle ne chiffre pas son contenu : toute personne qui possède le token
peut décoder le `payload`. Il ne faut donc jamais y placer de mot de passe,
donnée personnelle sensible, secret, ni autorisation devant pouvoir être retirée
immédiatement.

### Cookie d'authentification

Un cookie est une donnée conservée par le navigateur et jointe automatiquement
aux requêtes correspondant à son domaine et son chemin. Les attributs importants
sont :

| Attribut | Effet |
|---|---|
| `HttpOnly` | Empêche JavaScript de lire le cookie ; réduit l'impact d'un XSS sur le vol de token. |
| `Secure` | Envoie le cookie uniquement via HTTPS. |
| `SameSite` | Limite l'envoi inter-site du cookie ; contribue à la défense CSRF. |
| `Path=/` | Rend le cookie disponible pour toutes les routes de l'application. |
| Préfixe `__Host-` | Impose un cookie HTTPS, sans `Domain`, avec `Path=/` dans les navigateurs compatibles. |

### XSS

Une faille **Cross-Site Scripting** permet d'exécuter du JavaScript contrôlé par
un attaquant dans la page de l'application. Elle provient souvent de l'insertion
de texte non fiable avec `innerHTML`, de l'utilisation de bibliothèques
obsolètes, ou d'une CSP absente.

Avec un cookie `HttpOnly`, le script malveillant ne peut généralement pas lire
la valeur du JWT. Cela ne rend pas le XSS anodin : il peut envoyer des requêtes
authentifiées depuis la page, modifier l'interface, capturer des frappes ou
exfiltrer les données visibles.

### CSRF

Une attaque **Cross-Site Request Forgery** pousse le navigateur d'une victime
connectée à envoyer une requête vers l'application. Comme les cookies sont
automatiques, le serveur peut croire que cette requête vient de l'utilisateur.

XSS et CSRF sont donc différents :

- XSS : du code s'exécute *dans l'origine HBntory*.
- CSRF : une autre origine tente d'effectuer une action *vers HBntory*.

## 2. Fonctionnement dans HBntory aujourd'hui

Le flux est implémenté dans [auth.py](../backoffice/app/auth.py) :

```mermaid
sequenceDiagram
    participant U as Utilisateur
    participant B as Navigateur
    participant A as Backoffice FastAPI
    U->>B: Saisit identifiant et mot de passe
    B->>A: POST /auth/login (JSON)
    A->>A: Vérifie Argon2 et crée un JWT HS256
    A-->>B: Set-Cookie: access_token=JWT; HttpOnly; SameSite=Lax
    B->>A: Requête protégée + cookie automatique
    A->>A: Vérifie signature, exp, puis charge l'utilisateur
    A-->>B: Donnée ou 401/403
```

1. Le formulaire envoie `POST /auth/login` avec `credentials: 'include'`.
2. Le mot de passe est vérifié contre un hash Argon2.
3. Le serveur signe un JWT HS256 de 30 minutes par défaut et le place dans le
   cookie `access_token`.
4. Le JWT contient `sub`, `role`, `iat`, `exp` et, pour un utilisateur
   `common`, `branch_id`. Aucun mot de passe n'y est placé.
5. Les routes chargent de nouveau l'utilisateur depuis la base puis appliquent
   les contrôles de rôle (`admin` ou `common`) et d'agence.
6. La déconnexion demande au navigateur de supprimer le cookie. Un JWT déjà
   copié resterait toutefois cryptographiquement valable jusqu'à son expiration.

Le front ne stocke pas le JWT dans `localStorage` ni `sessionStorage`. C'est le
bon choix pour limiter le vol de token par XSS. Les appels `fetch` précisent
`credentials: 'include'`, ce qui permet l'envoi du cookie.

### Limites à connaître dans l'état actuel

- `SameSite=Lax` est une couche utile, mais il n'existe pas de jeton CSRF ni de
  vérification d'origine sur les méthodes qui modifient l'état (`POST`, `PATCH`,
  etc.). La protection CSRF n'est donc pas complète.
- `JWT_SECRET_KEY` a une valeur par défaut (`development-secret`). Elle doit
  provoquer l'arrêt du service en production si elle est absente ou faible.
- La déconnexion est locale au navigateur : il n'y a pas de liste de révocation
  côté serveur ni d'identifiant de session (`jti`) à invalider.
- Le rôle présent dans le JWT n'est pas la seule autorité : les routes protégées
  relisent l'utilisateur, ce qui est préférable. Toute décision sensible doit
  continuer à être prise à partir de la base et non du seul contenu du token.

## 3. Prévenir le XSS

### Règles de développement

1. Traiter toute donnée externe comme non fiable : saisie utilisateur, API
   produit, paramètres d'URL, messages d'erreur et données de base.
2. Insérer du texte avec `textContent` et créer les nœuds DOM avec
   `document.createElement`. Ne pas utiliser `innerHTML`, `outerHTML`,
   `insertAdjacentHTML` ou `document.write` avec des données non fiables.
3. Si du HTML riche est réellement nécessaire, le nettoyer avec une bibliothèque
   reconnue et configurée de façon restrictive (par exemple DOMPurify) avant
   affichage ; préférer le texte simple.
4. Ne jamais évaluer une chaîne comme du code (`eval`, `new Function`, handlers
   HTML `onclick=...`) et éviter les URL `javascript:`.
5. Valider côté serveur les formats, longueurs et types. L'échappement à
   l'affichage reste nécessaire, car validation et encodage ont des rôles
   différents.

### Content Security Policy (CSP)

Déployer une CSP d'abord en mode `Report-Only`, puis l'appliquer. Une cible
initiale, à ajuster aux ressources réellement utilisées, est :

```http
Content-Security-Policy:
  default-src 'self';
  base-uri 'self';
  object-src 'none';
  frame-ancestors 'none';
  form-action 'self';
  script-src 'self' 'nonce-{nonce_aleatoire}';
  style-src 'self';
  img-src 'self' data:;
  connect-src 'self';
  upgrade-insecure-requests
```

Une CSP ne corrige pas un XSS déjà présent, mais elle réduit les chemins
d'exploitation. En production, ajouter aussi au minimum :

```http
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
Permissions-Policy: camera=(), microphone=(), geolocation=()
Strict-Transport-Security: max-age=31536000; includeSubDomains
```

`Strict-Transport-Security` ne doit être activé qu'une fois HTTPS fonctionnel
pour le domaine concerné. Éviter `X-XSS-Protection`, obsolète.

## 4. Prévenir le CSRF avec un JWT en cookie

Un JWT dans un cookie est soumis au CSRF, car le navigateur joint le cookie sans
que le JavaScript appelant connaisse sa valeur. `HttpOnly` protège contre la
lecture par script, pas contre l'envoi automatique.

### Défense recommandée : jeton CSRF synchronisé

Pour chaque session, le serveur génère un secret aléatoire CSRF, le conserve côté
serveur (ou le lie cryptographiquement à la session) et donne au front une valeur
non sensible. Pour chaque requête qui change l'état :

1. le client envoie `X-CSRF-Token` ;
2. le serveur compare cette valeur à celle attendue, en temps constant ;
3. le serveur rejette la requête avec `403` en cas d'absence ou de divergence.

Le jeton CSRF peut être renvoyé par `GET /auth/csrf` ou intégré à une page
initiale. S'il est stocké dans un cookie lisible par JavaScript, il doit être
distinct du cookie d'authentification : c'est le modèle « double-submit », moins
fort sans liaison serveur mais acceptable quand il est signé ou lié à la session.

Compléter cette vérification par le refus des requêtes mutantes lorsque les
en-têtes `Origin` (prioritaire) ou `Referer` ne correspondent pas exactement à
l'origine HTTPS publique de HBntory. Ne pas se reposer uniquement sur CORS :
CORS empêche surtout le navigateur de lire une réponse, pas forcément d'émettre
une requête.

### Réglages cookie

En production, la cible est :

```http
Set-Cookie: __Host-access_token=<jwt>; Path=/; HttpOnly; Secure; SameSite=Strict
```

`SameSite=Strict` convient très bien à un backoffice utilisé uniquement sur son
propre domaine. Si un retour depuis une authentification externe ou un lien
inter-site est nécessaire, `Lax` peut être justifié, mais conserve le contrôle
CSRF explicite. `SameSite=None` nécessite `Secure` et un mécanisme CSRF robuste.

## 5. JWT, cookie ou session : quel choix ?

| Modèle | Avantages | Inconvénients | Usage conseillé |
|---|---|---|---|
| JWT dans `localStorage` + header `Authorization` | Simple côté API | Très exposé au vol par XSS | À éviter pour le backoffice |
| JWT dans cookie `HttpOnly` | Le token n'est pas lisible par JS | CSRF à gérer, révocation difficile sans état | Acceptable avec token court et CSRF |
| Session opaque dans cookie `HttpOnly` | Révocation immédiate, données/autorisation côté serveur | Stockage de sessions et disponibilité à gérer | Choix le plus simple et robuste pour un backoffice sensible |
| Access JWT court + refresh rotatif en cookie | Bon compromis pour plusieurs services | Conception et surveillance plus complexes | Architecture distribuée, équipe mature |

Pour HBntory, qui est un backoffice web monolithique, une **session opaque
stockée côté serveur** est généralement plus appropriée qu'un JWT : le besoin de
révocation (changement de mot de passe, désactivation d'utilisateur, incident)
est plus important que l'absence d'état côté serveur. Garder le JWT est viable
si les mesures de la section suivante sont mises en œuvre.

## 6. Cible « projet hyper sécurisé »

Priorité de mise en œuvre :

1. Forcer HTTPS derrière un proxy de confiance et rendre `Secure=True` sans
   exception en production. Refuser le démarrage si `JWT_SECRET_KEY` est absent,
   égal à la valeur de développement ou trop court ; le gérer dans un coffre à
   secrets et le faire tourner.
2. Ajouter un jeton CSRF obligatoire et une validation stricte de `Origin` pour
   `POST`, `PUT`, `PATCH` et `DELETE`.
3. Déployer la CSP et les en-têtes de sécurité, puis ajouter des tests de non
   régression XSS/CSRF.
4. Utiliser `__Host-access_token`, `Path=/`, `HttpOnly`, `Secure`,
   `SameSite=Strict` lorsque compatible avec le parcours utilisateur.
5. Émettre des access tokens très courts (5 à 15 minutes), avec `iss`, `aud`,
   `jti` et une liste de révocation, ou migrer vers une session opaque.
6. Pour un refresh token : rotation à chaque usage, conservation hachée côté
   serveur, détection de réutilisation, expiration absolue et invalidation de
   toutes les sessions lors d'un changement de mot de passe.
7. Ajouter limitation de débit et temporisation sur `/auth/login`, journaliser
   les échecs sans consigner mot de passe, JWT ou cookie, et proposer une MFA
   résistante au phishing (WebAuthn/passkey de préférence).
8. Restreindre CORS à des origines exactes et connues. Ne jamais associer
   `Access-Control-Allow-Origin: *` avec des cookies.
9. Mettre à jour les dépendances, analyser les vulnérabilités, séparer les
   comptes de service et effectuer revues de code, analyse SAST et tests
   d'intrusion réguliers.

## 7. Checklist de revue avant production

- [ ] HTTPS est obligatoire et les redirections HTTP sont contrôlées.
- [ ] Aucun secret de développement ni mot de passe de démonstration n'est actif.
- [ ] Les cookies d'authentification sont `HttpOnly`, `Secure`, `Path=/` et
      portent le `SameSite` adapté.
- [ ] Chaque action mutante exige un jeton CSRF et passe le contrôle d'origine.
- [ ] Aucun contenu non fiable n'est injecté via `innerHTML` sans sanitation.
- [ ] Une CSP est appliquée et ne contient pas `unsafe-inline` ou `unsafe-eval`.
- [ ] Les droits sont vérifiés côté serveur pour chaque route et chaque agence.
- [ ] L'utilisateur supprimé, désactivé ou dont le mot de passe a changé perd
      immédiatement ses sessions.
- [ ] Les tokens, cookies, mots de passe et en-têtes `Authorization` sont exclus
      des logs, traces et outils d'analytique.
- [ ] Des tests automatisés couvrent : token expiré/modifié, utilisateur supprimé,
      requête CSRF sans jeton, origine non autorisée et payload XSS affiché.

## Références

- [OWASP — Cross Site Scripting Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross_Site_Scripting_Prevention_Cheat_Sheet.html)
- [OWASP — Cross-Site Request Forgery Prevention Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html)
- [OWASP — JSON Web Token Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html)
- [MDN — Set-Cookie](https://developer.mozilla.org/docs/Web/HTTP/Reference/Headers/Set-Cookie)
