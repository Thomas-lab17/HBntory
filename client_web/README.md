# Client Web

Objectif : proposer une page publique minimale où un visiteur peut poser une
question sur les produits et les stocks, sans se connecter.

L'interface appellera le service IA, affichera un état de chargement puis une
réponse ou un message d'erreur explicite. Elle est distribuée par Nginx dans le
conteneur et accessible localement sur le port `8080` par défaut.
