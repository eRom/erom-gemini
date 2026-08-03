---
name: media
description: "Pose une question sur un fichier AUDIO, VIDÉO ou IMAGE (ou une URL YouTube/distante) via Antigravity (Gemini multimodal). Au-delà de la transcription — 'quelles décisions ont été prises ?', 'que se passe-t-il à 2:30 ?', 'quel est le ton de cette note vocale ?'. Claude Code ne voit/n'entend pas les médias ; Gemini si. Triggers : /erom-gemini:media, 'demande à la vidéo/l'audio', 'que dit cette image'. Sauve dans docs/gemini/media/."
---

Question-réponse multimodale sur un média : Gemini répond via `agy` en se basant sur ce qu'il a entendu/vu, avec repères temporels pour audio/vidéo.

Requête brute :
$ARGUMENTS

## Étape 0 — Racine du plugin

`ROOT` = `${CLAUDE_PLUGIN_ROOT}` s'il t'arrive expansé ; sinon deux niveaux au-dessus du « Base directory for this skill » injecté ci-dessus. `ROOT` est un chemin absolu, recopie-le littéralement dans les commandes ci-dessous.

## Étape 1 — Résoudre source + question (UN appel Bash)

Si `$ARGUMENTS` contient `--model <valeur>`, retire-le d'abord et garde `<valeur>` pour le header MODEL. Sépare le reste sur le premier `|` → gauche = source (URL ou fichier existant), droite = question. Sans `|`, le token URL/fichier en tête est la source, le reste la question. Question vide → demande une fois et stop.

```bash
python3 <ROOT>/scripts/agy/classify_source.py --mode media --src "<SOURCE>" --question "<QUESTION>"
mkdir -p docs/gemini/media
```

## Étape 2 — Déléguer à erom-gemini:gemini-run

Spawne UN subagent (tool Agent, `subagent_type: "erom-gemini:gemini-run"`) avec :

```
MODE: media
KIND: <KIND>
SOURCE: <chemin absolu ou URL>
ADD_DIR: <ADD_DIR (vide pour une URL)>
QUESTION: <question>
MODEL: <valeur de --model si présente, sinon vide>
WRITE_FILE: <WRITE_FILE>
CWD: <PWD absolu>
PLUGIN_ROOT: <ROOT>
```

## Étape 3 — Présenter

Présente la réponse verbatim puis le chemin sauvé. Ne retraite pas le média. Souci binaire/auth remonté par le subagent → relaie son message verbatim.

## Notes
- Pour audio/vidéo, la réponse cite des repères temporels (ex. "environ 02:30").
- Transcript complet plutôt qu'une réponse ciblée ? → `/erom-gemini:transcribe`. Breakdown visuel d'une vidéo ? → `/erom-gemini:video`.
