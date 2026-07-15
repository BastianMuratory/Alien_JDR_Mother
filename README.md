# Terminal de bord — Interface 2037

Un faux terminal d'ordinateur de bord façon *Alien* (MU-TH-UR 6500) pour tes parties du jeu de rôle **Alien**. Le Maître du Jeu joue l'IA du vaisseau depuis une console de contrôle ; chaque joueur voit un écran CRT vert phosphore sur lequel les réponses de l'IA s'affichent lettre par lettre, avec sons et effets d'écran cathodique.

Aucune dépendance : un seul fichier Python (bibliothèque standard) + un fichier HTML.

![Écran de connexion](captures/01-connexion.png)

## Démarrage rapide

1. Mets `serveur.py` et `index.html` dans le même dossier.
2. Lance le serveur :

   ```
   python serveur.py
   ```

3. **MJ** : ouvre `http://localhost:8000`, coche « Je suis le Maître du Jeu » et entre le code admin (par défaut `nostromo` — change-le en haut de `serveur.py`).
4. **Joueurs** (même réseau Wi-Fi) : ouvrent `http://IP-DE-TON-PC:8000` (l'IP est affichée au lancement du serveur).

## Côté joueur

![Terminal joueur](captures/02-terminal-joueur.png)

Le joueur entre le nom de son personnage et un **code d'accès personnel** : le code choisi à la première connexion est enregistré pour ce personnage, et sera exigé à chaque connexion suivante. Personne ne peut donc lire les conversations d'un autre en tapant simplement son nom.

Sur son terminal, le joueur ne voit que ce qui lui est adressé (canal privé ou diffusion générale). Il peut poser des questions à l'IA — elles n'arrivent qu'au MJ. Boutons en haut à droite : **AFFICHAGE** (ANIMÉ = lettre par lettre, INSTANT = messages affichés d'un bloc), **SON** (bips de frappe, alertes), **AMBRE** (thème orange), **CRT** (désactiver les effets d'écran). Ces préférences sont mémorisées par le navigateur.

## Côté MJ

![Console MJ](captures/03-console-mj.png)

La console MJ affiche un canal par joueur (pastille verte = en ligne, badge rouge = messages non lus) plus un canal **TOUS** pour la diffusion générale. Pour chaque message tu contrôles la **vitesse de frappe** sur l'écran du joueur, et tu disposes de boutons **⚠ ALERTE** (texte rouge + son d'alarme), **DÉMARRAGE** (séquence de boot sur son écran) et **EFFACER SON ÉCRAN**.

Au survol d'un message dans une conversation, un bouton **✕** apparaît : il supprime ce message précis, partout — historique serveur, console MJ, et lignes déjà affichées sur l'écran du joueur (même s'il est en train de s'écrire lettre par lettre, il disparaîtra). Fonctionne sur les messages de l'IA comme sur les questions des joueurs, et sur le fil de diffusion générale.

Sur le canal **TOUS**, le bouton **🗑 VIDER LE FIL** supprime tout l'historique de la diffusion générale (y compris pour les joueurs qui se reconnecteront) et efface l'écran de tous les joueurs — les canaux privés ne sont pas touchés.

Le bouton **RÉINIT. CODE** en haut d'un canal privé efface le code d'accès du personnage si un joueur l'a oublié : ses sessions sont déconnectées et il choisira un nouveau code à sa prochaine connexion.

### Messages rapides personnalisables

![Panneau des messages rapides](captures/04-messages-rapides.png)

Les puces au-dessus de la zone d'envoi insèrent des répliques prédéfinies (« ACCÈS REFUSÉ », « ANALYSE… », etc.). Le bouton **✎ GÉRER** ouvre un panneau pour les ajouter, modifier ou supprimer. Tout est sauvegardé automatiquement dans le navigateur et retrouvé d'une session à l'autre.

### Compte à rebours d'urgence

Le bouton **⏱ COMPTE À REBOURS** de la console MJ ouvre un panneau dédié pour lancer un minuteur diffusé à **tous** les joueurs. Sur leur terminal, tout l'écran bascule en **thème d'alerte rouge** et le temps restant s'affiche dans le bandeau du haut (alarme au lancement, bips sur les 10 dernières secondes, clignotement à zéro). **■ ARRÊTER** rend aux joueurs leur thème habituel (vert ou ambre). Quand un minuteur tourne, le bouton de la console affiche le temps restant en continu, panneau fermé.

Le curseur **Écoulement du temps** contrôle la vitesse réelle du minuteur, de ×0 (pause) à ×2 : pratique pour accorder discrètement un sursis aux joueurs ou mettre la pression. Rien ne trahit la manipulation côté joueur — les chiffres défilent simplement plus ou moins vite. Le minuteur est synchronisé par le serveur : tous les écrans affichent le même temps, et il survit à un rafraîchissement de page.

## Jouer à distance

Le plus simple : un tunnel Cloudflare (gratuit, sans compte), sans rien changer au code ni ouvrir de port sur ta box.

1. Télécharge `cloudflared` : https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/downloads/
2. Lance ton serveur normalement (`python serveur.py`).
3. Dans un second terminal :

   ```
   cloudflared tunnel --url http://localhost:8000
   ```

4. Envoie l'URL `https://xxxx.trycloudflare.com` affichée à tes joueurs.

L'URL change à chaque relance du tunnel ; ton PC doit rester allumé pendant la partie. Évite la redirection de port sur ta box : le tunnel n'expose que le site, pas ta machine.

## Fichiers et configuration

`serveur.py` : le serveur (HTTP + API JSON). En haut du fichier : `PORT`, `ADMIN_CODE` (code MJ — à changer !) et `PERSIST`. `index.html` : toute l'interface (joueur + MJ). `partie.json` : créé automatiquement — historique des messages et codes d'accès des personnages ; il survit aux redémarrages du serveur. Pour repartir de zéro, supprime-le. Les codes y sont stockés en clair : n'utilisez pas de vrais mots de passe.
