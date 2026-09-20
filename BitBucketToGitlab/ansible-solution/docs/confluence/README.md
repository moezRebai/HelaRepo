# Guide utilisateur Confluence — sections tranche 1

Ce répertoire contient le guide utilisateur destiné à être publié dans
Confluence (spec §6), en deux formats :

| Format | Fichiers | Usage |
|--------|----------|-------|
| **Markdown** | `01-vue-ensemble.md`, `02-guide-operateur.md`, `03-guide-developpeur.md`, `04-reference-exploitation.md` | Source versionnée, lisible directement dans le dépôt GitLab (revue, PR, historique) |
| **HTML storage format** | `01-vue-ensemble.storage.html`, `02-guide-operateur.storage.html`, `03-guide-developpeur.storage.html`, `04-reference-exploitation.storage.html` | Prêt à être collé/importé dans l'éditeur de page Confluence (format de stockage Confluence, proche du XHTML) |

Aucun connecteur API Confluence n'est autorisé (spec §8) : la publication
est **manuelle**. Le contenu Markdown est la source de vérité ; le HTML est
généré à partir du Markdown pour faciliter le collage dans Confluence.

## Contenu (4 parties)

- **A. Vue d'ensemble & concepts** (`01-vue-ensemble.md`) — introduction,
  carte des composants, glossaire.
- **B. Guide opérateur** (`02-guide-operateur.md`) — connexion AWX,
  lancement d'un job, planifications, dépannage.
- **C. Guide développeur** (`03-guide-developpeur.md`) — structure du
  dépôt, catalogue de conversion, règle convertir/encapsuler + Molecule,
  publication.
- **D. Référence & exploitation** (`04-reference-exploitation.md`) —
  secrets, Execution Environments, checklist de migration.

Voir aussi le [catalogue de conversion](../conversion-catalog.md), référencé
depuis la Partie C.

## Générer le HTML storage format

Prérequis : [pandoc](https://pandoc.org/installing.html).

```bash
for f in ansible-solution/docs/confluence/0*.md; do
  pandoc "$f" -f gfm -t html -o "${f%.md}.storage.html"
done
```

Cette commande convertit chaque page Markdown (`0*.md`) en HTML simple
(`gfm` → `html`), directement collable dans l'éditeur de page Confluence en
mode source (« Insert HTML » / éditeur de code source de la page). Rejouer
cette commande à chaque mise à jour d'une page Markdown avant republication
dans Confluence.

**Statut dans ce dépôt :** voir la note de génération ci-dessous — si
`pandoc` n'était pas disponible au moment de la livraison de cette tranche,
seul le Markdown a été livré et cette commande reste le prérequis documenté
pour produire le HTML.

## Publication manuelle dans Confluence

1. Générer (ou régénérer) les fichiers `.storage.html` avec la commande
   ci-dessus.
2. Dans Confluence, créer ou ouvrir la page correspondant à chaque partie
   (A/B/C/D), basculer l'éditeur en mode source (« Edit source » /
   insertion HTML brut selon la version de Confluence).
3. Coller le contenu du fichier `.storage.html` correspondant.
4. Vérifier le rendu (titres, tableaux, liens internes entre les 4 pages —
   à adapter en liens Confluence natifs si les pages sont séparées).
5. Publier la page.
