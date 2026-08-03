---
name: video
description: "REGARDE une vidéo et renvoie un breakdown VISUEL structuré (pas juste un transcript) via Antigravity (Gemini multimodal vidéo) — scènes horodatées, texte à l'écran/OCR (slides, graphiques, UI), moments clés. Pour screencasts, tutos, démos, présentations, inspections. Triggers : /erom-gemini:video, 'analyse cette vidéo', 'que montre cette vidéo'. Sauve dans docs/gemini/video/."
---

Donne des yeux à Claude sur une vidéo : Gemini la REGARDE via `agy` et renvoie un breakdown visuel horodaté (ce qui est montré, pas seulement dit). Pour un transcript pur, `/erom-gemini:transcribe` ; pour une question ciblée, `/erom-gemini:media`.

Requête brute :
$ARGUMENTS

## Étape 0 — Racine du plugin

`ROOT` = `${CLAUDE_PLUGIN_ROOT}` s'il t'arrive expansé ; sinon deux niveaux au-dessus du « Base directory for this skill » injecté ci-dessus. `ROOT` est un chemin absolu, recopie-le littéralement dans les commandes ci-dessous.

## Étape 1 — Résoudre source + kind (UN appel Bash)

Si `$ARGUMENTS` contient `--model <valeur>`, retire-le d'abord et garde `<valeur>` pour le header MODEL. Premier token restant URL ou fichier existant = source ; reste = focus. Rien → demande une fois « Quelle vidéo analyser (fichier ou URL) ? » et stop.

```bash
python3 <ROOT>/scripts/agy/classify_source.py --mode video --src "<SOURCE>"
mkdir -p docs/gemini/video
```

## Étape 2 — Déléguer à erom-gemini:gemini-run

Spawne UN subagent (tool Agent, `subagent_type: "erom-gemini:gemini-run"`) avec :

```
MODE: video
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

Présente le résumé d'abord, puis la table des scènes, puis le chemin sauvé. Ne retraite pas la vidéo. Souci binaire/auth remonté par le subagent → relaie son message verbatim.

## Notes
- Sortie = breakdown visuel : `## Résumé`, table `## Scènes`, `## Texte à l'écran`, `## Moments clés`.
- Vidéos > ~15 min : peuvent timeouter (le subagent monte le timeout à 12 min) ; découper avec `ffmpeg` si besoin.
