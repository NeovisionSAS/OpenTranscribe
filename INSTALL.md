# Installer OpenTranscribe sur un PC Windows

On dépose un fichier audio ou vidéo dans la page, on obtient la transcription complète en français, chaque passage attribué à un locuteur (renommable). La transcription et la reconnaissance des locuteurs passent par l'API pyannote.ai : pas de carte graphique nécessaire, pas de résumé IA.

Durée : 15 minutes de manipulations, puis 10 à 30 minutes de téléchargement la première fois.

## 1. Ce qu'il faut avant de commencer (une seule fois)

**Le PC**
- Windows 10 (22H2) ou Windows 11, 64 bits.
- 16 Go de mémoire vive conseillés (l'application en utilise environ 6 Go).
- 20 Go d'espace disque libre.

**Docker Desktop** (le logiciel qui fait tourner l'application)
1. Télécharger Docker Desktop : https://www.docker.com/products/docker-desktop/ → « Download for Windows ».
2. Lancer l'installateur, laisser cochée l'option **Use WSL 2 instead of Hyper-V**, terminer, **redémarrer le PC**.
3. Ouvrir Docker Desktop, accepter les conditions (pas besoin de créer de compte : « Skip »).
4. Attendre l'indication **Engine running** en bas à gauche.
5. Conseillé : Docker Desktop → Settings → General → cocher **Start Docker Desktop when you sign in to your computer**.

Si Docker demande de mettre à jour WSL : ouvrir PowerShell et taper `wsl --update`, puis relancer Docker Desktop.
Si Docker signale que la virtualisation est désactivée : elle s'active dans le BIOS du PC (demander au service informatique).

**Un compte pyannote.ai et une clé API** (c'est votre compte : les transcriptions vous sont facturées)
1. Aller sur https://dashboard.pyannote.ai et créer un compte (e-mail professionnel ou compte GitHub).
2. Dans le tableau de bord : section **API Keys** → **Create new key** → donner un nom (ex. « OpenTranscribe ») → **copier la clé** et la garder de côté (elle n'est plus affichée ensuite).
3. Coût : environ 1,60 € par heure d'audio transcrite (tarif relevé le 28/10/2026). Essai gratuit de 30 jours sans carte bancaire, puis formule Developer à 19 €/mois incluant 19 € de crédit. Tarifs à jour : https://www.pyannote.ai/pricing

## 2. Installer

1. Ouvrir **PowerShell** : touche Windows, taper `PowerShell`, Entrée.
2. Copier la ligne ci-dessous, la coller dans PowerShell (clic droit), appuyer sur Entrée :

```powershell
cd $HOME; Invoke-WebRequest https://github.com/NeovisionSAS/OpenTranscribe/archive/refs/heads/neovision.zip -OutFile OpenTranscribe.zip; Expand-Archive OpenTranscribe.zip -DestinationPath . -Force; cd OpenTranscribe-neovision; powershell -ExecutionPolicy Bypass -File .\install-windows.ps1
```

3. Quand le script le demande, coller la **clé API pyannote.ai** (clic droit) puis Entrée.
4. Attendre. À la fin, le script affiche :
   - l'adresse de la page : http://localhost:5173
   - l'identifiant (`admin@example.com`) et le mot de passe ;
   
   puis ouvre la page dans le navigateur.

L'application est installée dans le dossier `OpenTranscribe-neovision` de votre dossier utilisateur. L'identifiant, le mot de passe et la clé pyannote.ai sont dans le fichier `.env` de ce dossier (lignes `INITIAL_ADMIN_EMAIL`, `INITIAL_ADMIN_PASSWORD`, `PYANNOTE_API_KEY`).

## 3. Utiliser

1. Ouvrir http://localhost:5173 et se connecter.
2. Glisser un fichier audio ou vidéo sur la page.
3. Attendre la fin du traitement, puis ouvrir le fichier : transcription en français, découpée par locuteur. Cliquer sur un locuteur pour lui donner son vrai nom.

La page n'est accessible que depuis ce PC.

## 4. Au quotidien

- **Après un redémarrage** : Docker Desktop doit être lancé (automatique si l'option de l'étape 1 est cochée) ; l'application redémarre seule, la page revient au bout d'une minute ou deux.
- **Arrêter l'application** : Docker Desktop → Containers → bouton stop sur `opentranscribe-neovision`. Pour la relancer : bouton play, ou relancer l'installation (étape 2, point 2).
- **Mettre à jour** : refaire l'étape 2. Les transcriptions, le mot de passe et la clé sont conservés.
- **Changer de clé pyannote.ai** : modifier la ligne `PYANNOTE_API_KEY=` dans le fichier `.env` (Bloc-notes), puis relancer `install-windows.ps1`.

## 5. En cas de problème

| Message ou symptôme | Que faire |
|---|---|
| « Docker est introuvable » | Installer Docker Desktop (étape 1), redémarrer le PC. |
| « Docker Desktop n'est pas démarré » | Ouvrir Docker Desktop, attendre « Engine running », relancer la commande. |
| Un fichier reste en erreur | Vérifier sur https://dashboard.pyannote.ai que la clé est active et qu'il reste du crédit. |
| Le port 5173 est déjà utilisé | Ajouter la ligne `FRONTEND_PORT=5273` dans `.env`, relancer `install-windows.ps1`, puis ouvrir http://localhost:5273 |
| « La page ne répond pas » | Envoyer à la personne qui vous aide la sortie de `docker compose ps` et `docker compose logs backend --tail 50` (à taper dans PowerShell, dans le dossier `OpenTranscribe-neovision`). |
