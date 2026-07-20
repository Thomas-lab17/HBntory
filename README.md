# HBntory — Plan technique

## Stack technique choisie

| Besoin | Technologie |
|---|---|
| Backend Backoffice | Python + FastAPI |
| Base de données | PostgreSQL |
| Modèles de données | SQLAlchemy |
| Migrations de base de données | Alembic |
| Validation des requêtes | Pydantic |
| Authentification | JWT dans cookie sécurisé HttpOnly |
| Hashage des mots de passe | Argon2 ou bcrypt |
| Interface Backoffice | HTML, CSS, JavaScript |
| Interface Client public | HTML, CSS, JavaScript |
| Communication frontend/backend | API REST avec JSON |
| API Product externe | Requêtes HTTP REST |
| Serveur MCP | Python + SDK/framework MCP |
| Service IA | Python + FastAPI |
| Tests | Pytest |
| Variables sensibles | Fichier  non versionné |

## Architecture retenue



## Décisions principales

### Backend Python avec FastAPI

Nous utilisons Python et FastAPI pour le Backoffice et le service IA.

Avantage : FastAPI permet de créer rapidement des endpoints REST, de valider les données et de documenter automatiquement les APIs.

Limite : il faut organiser clairement les routes, services et permissions pour éviter un backend désordonné.

### PostgreSQL et SQLAlchemy

Nous utilisons PostgreSQL pour les données locales et SQLAlchemy pour les modèles.

Données enregistrées localement :
- utilisateurs ;
- agences ;
- stock par agence ;
- identifiant externe des produits ;
- rôles ;
- mots de passe hachés ;
- statut des utilisateurs supprimés.

Les détails produit ne sont pas stockés localement. Ils viennent toujours de l’API Product.

### JWT pour l’authentification

Nous utilisons des JWT pour identifier l’utilisateur connecté.

Le JWT contient au minimum :
- l’identifiant utilisateur ;
- son rôle ;
- son agence, si c’est un utilisateur commun ;
- une date d’expiration.

Le JWT doit être placé dans un cookie ,  en production et . Cela évite que JavaScript puisse lire directement le token.

Avantage : le frontend et le backend communiquent facilement avec une API REST.

Limite : il faut gérer l’expiration et, si nécessaire, l’invalidation des tokens. À chaque requête sensible, le backend vérifiera aussi que l’utilisateur existe encore et qu’il n’est pas supprimé.

### Interface HTML, CSS et JavaScript

Les deux interfaces seront simples et sans framework frontend complexe.

- Le Backoffice permet la connexion, la gestion de stock et la gestion des utilisateurs.
- Le Client public permet de poser une question à l’IA.

Avantage : développement plus rapide et moins de complexité.

Limite : l’interface sera moins riche qu’une application React, mais cela est suffisant pour le MVP.

---

# Plan de réalisation

## Étape 1 — Préparer le projet

Technologies : Git, Python, FastAPI, PostgreSQL, .

- Créer les projets Python.
- Configurer PostgreSQL.
- Ajouter les variables d’environnement.
- Définir les services et le diagramme.
- Définir les endpoints REST.
- Définir les rôles  et .

Résultat attendu : architecture validée avant de coder les fonctionnalités.

## Étape 2 — Base de données et Backoffice API

Technologies : PostgreSQL, SQLAlchemy, Alembic, Pydantic.

- Créer les tables fdbrv__,  et .
- Créer les relations SQLAlchemy.
- Ajouter les migrations Alembic.
- Créer un script de données initiales :
  - un administrateur ;
  - deux agences ;
  - du stock de test.
- Stocker uniquement  dans la table de stock.
- Mettre les règles de validation de stock dans le backend.

Résultat attendu : la base est initialisable et les règles de stock sont protégées côté serveur.

## Étape 3 — Sécurité et rôles

Technologies : JWT, Argon2 ou bcrypt, FastAPI Security.

- Créer la connexion.
- Hacher les mots de passe.
- Générer un JWT après connexion.
- Protéger les endpoints Backoffice.
- Refuser les utilisateurs supprimés.
- Autoriser :
  - l’admin à gérer les utilisateurs ;
  - l’utilisateur commun à gérer uniquement le stock de son agence.
- Interdire :
  - à l’admin de modifier le stock ;
  - à l’utilisateur commun de gérer les utilisateurs ou une autre agence.

Résultat attendu : les autorisations sont vérifiées dans le backend.

## Étape 4 — Fonctionnalités Backoffice

Technologies : FastAPI, HTML, CSS, JavaScript, Fetch API.

- Créer les endpoints de stock :
  - lister le stock ;
  - ajouter du stock ;
  - retirer du stock ;
  - consulter la quantité d’un produit.
- Créer les endpoints administrateur :
  - lister les utilisateurs ;
  - créer un utilisateur ;
  - changer son agence ;
  - changer son mot de passe ;
  - supprimer logiquement un utilisateur.
- Connecter le Backoffice à l’API Product pour vérifier les identifiants et afficher les détails produit.
- Créer les pages HTML/JS du Backoffice.

Résultat attendu : un utilisateur commun gère son agence et l’admin gère les comptes.

## Étape 5 — Product MCP Server

Technologies : Python, MCP, client HTTP.

- Créer le serveur MCP.
- Ajouter l’outil .
- Ajouter l’outil .
- Appeler l’API Product externe.
- Gérer clairement :
  - produit inconnu ;
  - erreur réseau ;
  - API Product indisponible.
- Tester les outils manuellement.

Résultat attendu : l’IA peut obtenir des données produit réelles via MCP.

## Étape 6 — AI Query Service

Technologies : Python, FastAPI, MCP client, client HTTP, fournisseur LLM.

- Créer une API interne de stock en lecture seule.
- Créer le service IA.
- Connecter l’agent aux outils MCP Product.
- Connecter le service IA à l’API de stock.
- Accepter les questions sur :
  - les détails d’un produit ;
  - les agences où un produit est disponible ;
  - les produits disponibles dans une agence ;
  - une liste de courses et les quantités souhaitées.
- Refuser clairement les questions hors périmètre.
- Enregistrer les appels d’outils dans les logs pour faciliter le débogage.

Résultat attendu : les réponses IA sont fondées sur les produits et stocks réellement récupérés.

## Étape 7 — Client public

Technologies : HTML, CSS, JavaScript, Fetch API.

- Créer une page avec un champ de question.
- Ajouter un bouton d’envoi.
- Appeler  du service IA.
- Afficher un chargement pendant la réponse.
- Afficher la réponse ou une erreur claire.

Résultat attendu : un visiteur peut poser une question sans se connecter.

## Étape 8 — Tests, documentation et démo

Technologies : Pytest, documentation Markdown.

- Tester le stock négatif.
- Tester l’interdiction d’accès à une autre agence.
- Tester les rôles admin/utilisateur commun.
- Tester la suppression logique.
- Tester les produits inconnus.
- Tester les réponses IA et erreurs API.
- Écrire le README.
- Préparer la démo finale.

Résultat attendu : le système complet peut être lancé et démontré.

---

# Répartition conseillée à trois

| Personne | Responsabilité |
|---|---|
| Personne 1 | Base PostgreSQL, SQLAlchemy, migrations, JWT, rôles, API Backoffice. |
| Personne 2 | Product API, MCP Server, API stock interne, AI Query Service. |
| Personne 3 | Pages HTML/CSS/JS Backoffice et Client, tests interface, README, présentation. |

Tous participent à l’intégration finale et aux tests.

---

# MVP à terminer avant tout

- Authentification JWT sécurisée.
- Utilisateurs, agences et stock dans PostgreSQL.
- Ajout/retrait de stock avec règles de sécurité.
- Gestion des utilisateurs par l’admin.
- API Product connectée.
- MCP avec liste et détail produit.
- Service IA avec les quatre types de questions imposés.
- Interface Client simple.
- README et démonstration.

Les améliorations visuelles, tableaux de bord, historique de stock, streaming IA et déploiement sont optionnels.
