---
name: doc-to-md
description: "Convertit un PDF, docx, image ou HTML en Markdown propre via Antigravity (Gemini multimodal) — tables, titres, listes préservés, langue d'origine conservée. Triggers : /erom-gemini:doc-to-md, 'convertis ce PDF/docx en markdown', 'OCR ce document'. Sauve dans docs/gemini/converted/."
---

Convertit un document en Markdown en offloadant l'OCR/lecture multimodale vers Gemini via `agy`.

Requête brute :
$ARGUMENTS

## Étape 0 — Racine du plugin

`ROOT` = `${CLAUDE_PLUGIN_ROOT}` s'il t'arrive expansé ; sinon deux niveaux au-dessus du « Base directory for this skill » injecté ci-dessus. `ROOT` est un chemin absolu, recopie-le littéralement dans les commandes ci-dessous.

## Étape 1 — Résoudre la source (UN appel Bash)

Si `$ARGUMENTS` contient `--model <valeur>`, retire-le d'abord (ce n'est pas le focus) et garde `<valeur>` pour le header MODEL. Le premier token restant qui existe (`test -f`) est le fichier ; le reste est un focus optionnel. Aucun fichier valide → demande une fois « Quel fichier convertir ? » et stop.

```bash
python3 <ROOT>/scripts/agy/classify_source.py --mode doc-to-md --src "<FICHIER>"
mkdir -p docs/gemini/converted
```

## Étape 2 — Déléguer à erom-gemini:gemini-run

Spawne UN subagent (tool Agent, `subagent_type: "erom-gemini:gemini-run"`) avec ce header (FOCUS = le texte restant, ou vide) :

```
MODE: doc-to-md
KIND: <KIND de l'étape 1>
SOURCE: <chemin absolu du fichier>
ADD_DIR: <ADD_DIR de l'étape 1>
FOCUS: <focus ou vide>
MODEL: <valeur de --model si présente, sinon vide>
WRITE_FILE: <WRITE_FILE de l'étape 1>
CWD: <PWD absolu>
PLUGIN_ROOT: <ROOT>
```

## Étape 3 — Présenter

Le subagent lit et retourne le fichier. Présente les ~30 premières lignes de la conversion puis le chemin sauvé. Ne retraite pas le document toi-même. Si le subagent remonte un souci binaire/auth, relaie son message verbatim (installation ou ré-auth).

## Notes
- Documents > 20 pages : signale-le dans FOCUS (ex. « 45 pages ») pour que le subagent monte son timeout à 15 min.
