# PSE25-27 Révision

Jeu de révision (Quiz + Flashcards) pour réviser les modules PSE 25-27 / PSE Expert Réseau
et les autres fascicules du dépôt, jouable entièrement à la manette sur Batocera.

## Contenu

165+ modules répartis en 9 séries thématiques (cybersécurité, numérique de l'État,
Bercy/finances publiques, PSE 25-27, PSE Expert Réseau...), chacun avec :

- un mode **Quiz** : QCM chronométré, 15 questions tirées aléatoirement parmi celles du module
- un mode **Flashcards** : cartes recto/verso navigables, à retourner pour vérifier la réponse
- **Synthèse vocale française** (bouton R1) sur les questions/choix/explications du quiz et
  sur chaque face des flashcards, voir la section dédiée ci-dessous

## Contrôles manette

- D-pad / stick analogique / Select-Start : naviguer dans les menus et les listes
- **A** : valider / retourner une flashcard
- **B** : retour à l'écran précédent
- Gauche/Droite : carte précédente/suivante (en mode Flashcards)
- En quiz : **A/B/C/D** (esprit manette NeoGeo) répondent directement au choix correspondant ; **L1** abandonne la question
- **R1** : lire à voix haute (flashcard affichée, ou question + choix en quiz/explication en feedback)

## Synthèse vocale (R1)

Voix française neuronale locale ([Piper](https://github.com/rhasspy/piper), voix
`fr_FR-siwis-medium`), embarquée dans `tts_assets/` (binaire + modèle, ~112 Mo, aucune
dépendance réseau). Mesuré sur le CPU de la machine Batocera cible : la synthèse est
~1,5× plus lente que le temps réel (une phrase de 20 mots prend environ 10 à 15
secondes à générer, contre une fraction de seconde sur une machine de développement
plus puissante). Une lecture à la volée bloquerait donc le jeu de façon inacceptable.

Solution retenue : chaque contenu (recto/verso d'une carte, question+choix d'un quiz,
explication) est synthétisé **une seule fois**, dans un thread d'arrière-plan, et mis en
cache sous forme de fichier `.wav` dans `tts_assets/cache/` (persistant sur le disque de
la machine). Un badge « VOIX : préparation… » puis « VOIX : lecture… » s'affiche en
haut à droite de l'écran pendant ce délai. Toute lecture suivante du même contenu est
instantanée. Le cache se remplit donc progressivement à l'usage ; il peut être vidé
(dossier `tts_assets/cache/`) sans risque, il se regénère à la demande.

## Origine des données

Les fichiers `data/quizz/*.csv` et `data/flashcard/*.csv` proviennent du dépôt de révision
PSE25-27 (généré à partir des fascicules officiels du parcours). `data/modules.json` liste
les modules disponibles par série.

## Licence

Code du jeu : usage personnel. Police intégrée : DejaVu Sans (licence Bitstream Vera /
DejaVu, libre de redistribution).
