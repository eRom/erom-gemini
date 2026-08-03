---
name: transcribe
description: "Transcrit et résume un fichier AUDIO ou VIDÉO (ou une URL YouTube/distante) via Antigravity (Gemini multimodal) — ce que Claude Code ne sait pas faire nativement. Notes vocales, réunions, appels, screencasts. Transcript fidèle + résumé ; timestamps pour vidéo/URL. Triggers : /erom-gemini:transcribe, 'transcris cet audio/cette vidéo'. Sauve dans docs/gemini/transcripts/."
---

Offloade la compréhension audio/vidéo vers Gemini via `agy` (Gemini est nativement multimodal ; Claude Code non).

Requête brute :
$ARGUMENTS

## Étape 0 — Racine du plugin

`ROOT` = `${CLAUDE_PLUGIN_ROOT}` s'il t'arrive expansé ; sinon deux niveaux au-dessus du « Base directory for this skill » injecté ci-dessus. `ROOT` est un chemin absolu, recopie-le littéralement dans les commandes ci-dessous.

## Étape 1 — Résoudre source + kind (UN appel Bash)

Si `$ARGUMENTS` contient `--model <valeur>`, retire-le d'abord et garde `<valeur>` pour le header MODEL. Le premier token restant qui est une URL (`http(s)://`) OU un fichier existant (`test -f`) est la source ; le reste est un focus optionnel. Rien ne résout → demande une fois « Quel audio/vidéo/URL transcrire ? » et stop.

```bash
python3 <ROOT>/scripts/agy/classify_source.py --mode transcribe --src "<SOURCE>"
mkdir -p docs/gemini/transcripts
```

## Étape 2 — Déléguer à erom-gemini:gemini-run

Spawne UN subagent (tool Agent, `subagent_type: "erom-gemini:gemini-run"`) avec :

```
MODE: transcribe
KIND: <KIND>
SOURCE: <chemin absolu ou URL>
ADD_DIR: <ADD_DIR (vide pour une URL)>
FOCUS: <focus ou vide>
MODEL: <valeur de --model si présente, sinon vide>
WRITE_FILE: <WRITE_FILE>
CWD: <PWD absolu>
PLUGIN_ROOT: <ROOT>
```

## Étape 3 — Présenter

Lis ce que retourne le subagent : le résumé d'abord, puis le chemin du transcript. Ne retraite pas le média. Souci binaire/auth remonté par le subagent → relaie son message verbatim.

## Notes
- Formats audio (ogg/opus/mp3/wav/m4a/flac) et vidéo (mp4/mov/webm…) courants ; YouTube et URLs publiques marchent sans téléchargement.
- Fichiers > ~30 min : découper avec `ffmpeg` d'abord si timeout.
- Breakdown visuel horodaté plutôt qu'un transcript ? → `/erom-gemini:video`. Question ciblée ? → `/erom-gemini:media`.
