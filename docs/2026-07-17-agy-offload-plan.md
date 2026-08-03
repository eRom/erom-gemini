# agy-offload — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Donner à Claude Code des oreilles/yeux (audio, vidéo, image, OCR docs) et un deep-research multi-rounds groundé Google, en offloadant le travail lourd vers Antigravity CLI (`agy`, Gemini) facturé au Google AI Pro de Romain.

**Architecture:** Import natif dans `~/.claude` (repo git existant), sans fork GitHub ni format plugin. Un subagent forwarder unique `agy-run` porte le contrat d'invocation agy et les prompts par mode ; cinq skills user-invocables (`/transcribe`, `/video`, `/media`, `/doc-to-md`, `/agy-deep`) préparent les arguments et délèguent à `agy-run` — le pattern exact des skills `devil-code`/`devil-spec` de Romain. Le deep-research passe par un Workflow déterministe. Scripts partagés sous `~/.claude/scripts/agy/`.

**Tech Stack:** Markdown (subagent + skills), Python 3 stdlib (classifieur, scratch runner), JavaScript/ESM sous `bun` (Workflow + lib de rendu), `agy` 1.1.3 CLI.

## Global Constraints

- Plateforme unique **macOS** : ignorer toute la logique Windows du repo source (Defender/#217, cygpath, `.exe`).
- Contrat d'invocation agy (vérifié sur agy **1.1.3** local, ping headless OK 2026-07-17), non négociable sur chaque appel : `agy --dangerously-skip-permissions [--add-dir <dir>]... [--model '<label>'] --print-timeout <N> --print "<prompt>" < /dev/null`. `--print` DERNIER flag ; `< /dev/null` obligatoire ; timeout Bash = timeout agy + 60 s.
- Réponse agy **toujours écrite dans un fichier** (`write_file`), jamais lue depuis stdout ; vérifier `test -s <fichier>` après exit 0 ; sinon plan B transcript, sinon échec verbeux.
- Modèle par défaut partout : `Gemini 3.5 Flash (High)` (label EXACT de `agy models` ; label inconnu = fallback silencieux). Override via flag `--model` per-invocation, **jamais** via settings.json (global, race).
- Override modèle : les 4 skills multimodales acceptent un `--model <alias|label>` optionnel — le retirer de `$ARGUMENTS` avant de calculer le focus/la question, et le passer dans le header `MODEL:` (agy-run résout les alias). `/agy-deep` n'expose PAS d'override (le modèle est géré par angle dans le Workflow ; déviation assumée vs « les 5 skills » de la spec — threading un modèle à travers args→deep-agy.js→agent() serait du sur-mesure pour un override ponctuel, à faire en suivi si besoin).
- Langue de sortie : **français par défaut**, langue de la source si clairement autre ; transcripts et conversions jamais traduits (langue d'origine).
- Sorties sous `docs/agy/<kind>/` relatif au CWD du projet courant.
- Suppression de fichiers : `trash`, jamais `rm` — SAUF `rm -rf` sur un `mktemp -d` que la tâche vient de créer (temp jetable, jamais un chemin utilisateur).
- Outils : `bun` pour JS/TS, `python3` pour Python (scripts stdlib-only, pas de venv nécessaire).
- Git : commit direct sur `main` de `~/.claude`, un commit par tâche, fichiers additifs uniquement (ne casse aucun comportement existant). Chaque message se termine par les deux lignes Co-Authored-By / Claude-Session en vigueur.
- Source verbatim à copier : `~/dev/antigravity-plugin-cc-main/plugins/antigravity/` (licence MIT). Les copies `cp` référencent ce chemin réel sur disque.

---

## Phase 1 — Substrat + multimodal

### Task 1: Classifieur de source `classify_source.py`

**Files:**
- Create: `~/.claude/scripts/agy/classify_source.py`
- Test: `~/.claude/scripts/agy/tests/test_classify_source.py`

**Interfaces:**
- Produces: `classify(mode, src, question="", today=None) -> dict` avec clés `kind`, `add_dir`, `write_file` (absolu), `source`. `mode ∈ {transcribe, video, media, doc-to-md}`. CLI `--mode --src [--question]` imprime `KIND=/ADD_DIR=/WRITE_FILE=/SOURCE=`.

- [ ] **Step 1: Écrire le test qui échoue**

```python
# ~/.claude/scripts/agy/tests/test_classify_source.py
import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from classify_source import classify

class TestClassify(unittest.TestCase):
    def wf(self, r):
        return r["write_file"].replace(os.getcwd() + os.sep, "").replace(os.getcwd(), "")
    def test_transcribe_video_ext(self):
        r = classify("transcribe", "reunion.mp4")
        self.assertEqual(r["kind"], "video")
        self.assertTrue(self.wf(r).endswith("docs/agy/transcripts/reunion.md"))
    def test_transcribe_audio_default_and_slug(self):
        r = classify("transcribe", "note vocale.OGG")
        self.assertEqual(r["kind"], "audio")
        self.assertTrue(self.wf(r).endswith("docs/agy/transcripts/note-vocale.md"))
    def test_transcribe_url(self):
        r = classify("transcribe", "https://youtu.be/AbC_123")
        self.assertEqual(r["kind"], "url")
        self.assertEqual(r["add_dir"], "")
        self.assertTrue(self.wf(r).endswith("docs/agy/transcripts/youtu-be-abc-123.md"))
    def test_video_url(self):
        r = classify("video", "https://www.example.com/demo")
        self.assertEqual(r["kind"], "url")
        self.assertTrue(self.wf(r).endswith("docs/agy/video/example-com-demo.md"))
    def test_media_video_with_question_hash(self):
        r = classify("media", "clip.MOV", "que decide-t-on a 2:30?")
        self.assertEqual(r["kind"], "video")
        self.assertRegex(self.wf(r), r"docs/agy/media/clip-[0-9a-f]{6}\.md$")
    def test_media_image(self):
        r = classify("media", "photo.JPEG", "quoi?")
        self.assertEqual(r["kind"], "image")
    def test_doc_to_md_pdf_dated(self):
        r = classify("doc-to-md", "Contrat Final.PDF", today="2026-07-17")
        self.assertEqual(r["kind"], "pdf")
        self.assertTrue(self.wf(r).endswith("docs/agy/converted/2026-07-17-contrat-final.md"))
    def test_doc_to_md_html_and_image_and_other(self):
        self.assertEqual(classify("doc-to-md", "page.HTM")["kind"], "html")
        self.assertEqual(classify("doc-to-md", "scan.png")["kind"], "image")
        self.assertEqual(classify("doc-to-md", "data.xyz")["kind"], "other")
    def test_file_add_dir_is_absolute(self):
        r = classify("transcribe", "reunion.mp4")
        self.assertTrue(os.path.isabs(r["add_dir"]))

if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Lancer le test, vérifier l'échec**

Run: `python3 ~/.claude/scripts/agy/tests/test_classify_source.py`
Expected: FAIL avec `ModuleNotFoundError: No module named 'classify_source'`.

- [ ] **Step 3: Écrire l'implémentation** (logique pré-validée 2026-07-17)

```python
# ~/.claude/scripts/agy/classify_source.py
#!/usr/bin/env python3
"""Classifie une source (fichier local ou URL) pour les skills agy multimodales.
Renvoie kind / add_dir / write_file / source. Aucune dépendance hors stdlib."""
import os, re, hashlib, datetime

AUD = (".ogg", ".mp3", ".wav", ".m4a", ".aac", ".flac", ".opus", ".aiff")
VID = (".mp4", ".mov", ".webm", ".mkv", ".avi", ".m4v")
IMG = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def _slug(s, n):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:n]


def _base(src, is_url, n):
    if is_url:
        return _slug(re.sub(r"^https?://(www\.)?", "", src.lower()), n) or "url"
    return _slug(os.path.splitext(os.path.basename(src))[0], n) or "media"


def classify(mode, src, question="", today=None):
    src = src.strip().strip('"')
    low = src.lower()
    is_url = low.startswith("http")
    today = today or datetime.date.today().isoformat()
    if mode == "transcribe":
        kind = "url" if is_url else ("video" if low.endswith(VID) else "audio")
        out = os.path.join("docs", "agy", "transcripts", f"{_base(src, is_url, 50)}.md")
    elif mode == "video":
        kind = "url" if is_url else "file"
        out = os.path.join("docs", "agy", "video", f"{_base(src, is_url, 50)}.md")
    elif mode == "media":
        if is_url:
            kind = "url"
        elif low.endswith(VID):
            kind = "video"
        elif low.endswith(AUD):
            kind = "audio"
        elif low.endswith(IMG):
            kind = "image"
        else:
            kind = "file"
        qh = hashlib.sha1(question.encode()).hexdigest()[:6]
        out = os.path.join("docs", "agy", "media", f"{_base(src, is_url, 40)}-{qh}.md")
    elif mode == "doc-to-md":
        ext = os.path.splitext(low)[1]
        kind = ("pdf" if ext == ".pdf" else "docx" if ext in (".docx", ".doc")
                else "image" if ext in IMG else "html" if ext in (".html", ".htm") else "other")
        base = _slug(os.path.splitext(os.path.basename(src))[0], 60) or "doc"
        out = os.path.join("docs", "agy", "converted", f"{today}-{base}.md")
    else:
        raise SystemExit(f"unknown mode: {mode}")
    add_dir = "" if is_url else os.path.dirname(os.path.abspath(src))
    return {"kind": kind, "add_dir": add_dir, "write_file": os.path.abspath(out), "source": src}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--question", default="")
    a = ap.parse_args()
    r = classify(a.mode, a.src, a.question)
    print(f"KIND={r['kind']}")
    print(f"ADD_DIR={r['add_dir']}")
    print(f"WRITE_FILE={r['write_file']}")
    print(f"SOURCE={r['source']}")
```

- [ ] **Step 4: Lancer le test, vérifier le succès**

Run: `python3 ~/.claude/scripts/agy/tests/test_classify_source.py`
Expected: `OK` (10 tests).

- [ ] **Step 5: Commit**

```bash
cd ~/.claude && git add scripts/agy/classify_source.py scripts/agy/tests/test_classify_source.py
git commit -m "feat(agy): classifieur de source multimodal + tests"
```

---

### Task 2: Subagent forwarder `agy-run` (modes multimodaux)

**Files:**
- Create: `~/.claude/agents/agy-run.md`
- Create: `~/.claude/scripts/agy/recover_transcript.py` (récupération plan B — extraite en script pour éviter le heredoc fragile qu'un subagent LLM doit reconstituer)
- Test: `~/.claude/scripts/agy/tests/test_recover_transcript.py`

**Interfaces:**
- Consumes: header block MODE/KIND/SOURCE/ADD_DIR/FOCUS/QUESTION/MODEL/WRITE_FILE/CWD passé par les skills.
- Produces: lit `WRITE_FILE`, retourne son contenu verbatim (résumé + chemin). Modes de cette tâche : `transcribe`, `video`, `media`, `doc-to-md`. `recover_transcript.py` expose `recover(path) -> str|None` (dernier `MODEL/PLANNER_RESPONSE.content` d'un transcript.jsonl) + CLI `python3 recover_transcript.py <transcript.jsonl>` qui imprime le contenu récupéré (rien si absent).

- [ ] **Step 1: Écrire le fichier subagent**

Créer `~/.claude/agents/agy-run.md` avec ce contenu exact :

````markdown
---
name: agy-run
description: Forwarder vers Antigravity CLI (agy / Gemini) pour les capacités où Claude Code est faible : transcription audio/vidéo, breakdown visuel vidéo, Q&A multimodal, OCR document→markdown, et angles/red-team de deep-research. Réservé aux skills agy-* (transcribe/video/media/doc-to-md/agy-deep) — ne pas utiliser pour déléguer librement.
color: green
tools: Bash, Read
model: haiku
---

Tu es un forwarder mince autour de `agy --print`. Tu reçois un header, tu lances UN appel agy, tu lis le fichier de sortie, tu retournes son contenu verbatim. Tu n'explores pas le repo, tu ne paraphrases pas.

## Résolution du binaire

`$AGY_BIN` si défini, sinon `agy` sur PATH, sinon `${HOME}/.local/bin/agy`. Absent → retourne : « agy introuvable : installer https://antigravity.google, puis lancer `agy` une fois en terminal pour l'OAuth » et stop.

## Contrat d'invocation (non négociable)

```
agy --dangerously-skip-permissions [--add-dir <dir>]... --model '<MODEL ou "Gemini 3.5 Flash (High)">' --print-timeout <N> --print "<PROMPT>" < /dev/null
```

- `--print` est le DERNIER flag avant le prompt (le parseur Go consomme le token suivant).
- `< /dev/null` après le prompt est OBLIGATOIRE (stdin hérité ouvert = hang non borné par --print-timeout).
- Timeout de l'outil Bash = timeout agy + 60 s, toujours explicite.
- Échappe les `"` internes du prompt en `\"`.
- MODEL : si le header fournit un MODEL non vide, résous-le via la table d'alias ci-dessous (une valeur absente de la table est passée telle quelle, supposée être un label exact) ; sinon `Gemini 3.5 Flash (High)`.

Table d'alias (reprise de `config/model-map.json` du repo ; label exact = chaîne de `agy models`) :

| Alias | Label |
|---|---|
| `flash-low` | `Gemini 3.5 Flash (Low)` |
| `flash` / `flash-medium` | `Gemini 3.5 Flash (Medium)` |
| `flash-high` | `Gemini 3.5 Flash (High)` |
| `pro` / `pro-low` | `Gemini 3.1 Pro (Low)` |
| `pro-high` | `Gemini 3.1 Pro (High)` |
| `sonnet` | `Claude Sonnet 4.6 (Thinking)` |
| `opus` | `Claude Opus 4.6 (Thinking)` |
| `gpt-oss` | `GPT-OSS 120B (Medium)` |

## Après l'appel : vérifier puis récupérer

1. `test -s "<WRITE_FILE>"` : si non vide, `Read` le fichier et retourne (résumé d'abord, chemin ensuite). Fini.
2. Sinon, UN appel Bash pour trier via le dernier log :
   ```bash
   LOG=$(ls -t ~/.gemini/antigravity-cli/log/cli-*.log 2>/dev/null | head -1)
   grep -oE 'auth timed out|keyringAuth: timed out|text_drip.*length=[0-9]+' "$LOG" | tail -3
   ```
   - `auth timed out` / `keyringAuth: timed out` → retourne : « agy : auth headless expirée (le modèle n'a pas tourné). Lancer `agy` une fois dans un vrai terminal pour rafraîchir l'OAuth, puis réessayer. » NE PAS retry.
   - sinon (réponse générée mais stdout/fichier perdu) → plan B transcript, UN appel Bash (script dédié — pas de heredoc, robuste à l'indentation markdown) :
     ```bash
     CID=$(grep -oE 'conversation=[0-9a-f-]{36}' "$LOG" | tail -1 | cut -d= -f2)
     TX="$HOME/.gemini/antigravity-cli/brain/$CID/.system_generated/logs/transcript.jsonl"
     [ -n "$CID" ] && [ -f "$TX" ] && python3 ~/.claude/scripts/agy/recover_transcript.py "$TX"
     ```
     Retourne le contenu récupéré. Si vide aussi : retourne l'échec verbeux (les 8 dernières lignes du log).

## Modes

Chaque prompt se termine par : « OUTPUT REQUIREMENT (CRITIQUE) : n'imprime rien dans le chat. Le fichier écrit à `<WRITE_FILE>` est ton seul livrable. »

### MODE: transcribe
Timeout agy : `6m0s` si KIND=audio, `12m0s` si KIND=video|url. `--add-dir` : `<ADD_DIR>` (si non vide) ET `<CWD>`.
Prompt :
```
Tâche de transcription + résumé audio/vidéo.
Source (<KIND>) : <SOURCE>
Focus / à mettre en avant : <FOCUS ou "transcription fidèle et complète">
Écoute / regarde la source. Transcris-la INTÉGRALEMENT et fidèlement dans sa langue D'ORIGINE (ne traduis pas). Marque les passages incertains [inaudible]. Pour KIND = video ou url, préfixe chaque segment naturel d'un timestamp (mm:ss). Ajoute ensuite un court résumé dans la même langue.
Écris le résultat à ce chemin ABSOLU : <WRITE_FILE>, avec ces sections (en-têtes exacts) :
## Transcription   (timestamps pour video/url)
## Résumé          (2-5 lignes : points clés / décisions / actions selon FOCUS)
N'invente rien.
```

### MODE: video
Timeout agy : `12m0s`. `--add-dir` : `<ADD_DIR>` (si non vide) ET `<CWD>`.
Prompt :
```
Analyse vidéo — breakdown VISUEL. Langue de sortie : français, sauf si la vidéo est clairement dans une autre langue.
Source (<KIND>) : <SOURCE>
Focus : <FOCUS ou "breakdown visuel général">
REGARDE toute la vidéo. Décris ce qui est MONTRÉ, avec timestamps — pas seulement l'audio. Écris au chemin ABSOLU <WRITE_FILE> exactement ce Markdown :
## Résumé
<3-6 phrases : ce qu'est la vidéo, ce qui s'y passe, le takeaway>
## Scènes
| Tranche (mm:ss–mm:ss) | Ce qu'on voit | Texte à l'écran / OCR | Audio (résumé) |
|---|---|---|---|
(une ligne par segment cohérent ; couvre toute la durée dans l'ordre)
## Texte à l'écran
<TOUT le texte lisible à l'écran — puces de slides, sous-titres, code, UI, figures — groupé par timestamp ; c'est de l'OCR, transcris verbatim, marque "illisible" si illisible>
## Moments clés
- mm:ss — <événement visuel notable : un résultat affiché, une transition, une erreur, une frame clé>
Sois fidèle à ce qui est réellement visible ; n'invente aucun texte à l'écran ni événement.
```

### MODE: media
Timeout agy : `6m0s` si KIND ∈ {audio,image}, `12m0s` si KIND ∈ {video,url}. `--add-dir` : `<ADD_DIR>` (si non vide) ET `<CWD>`.
Prompt :
```
Tâche de question-réponse multimodale. Langue de sortie : français, sauf si la source ou la question est clairement dans une autre langue.
Source (<KIND>) : <SOURCE>
Question : <QUESTION>
Écoute / regarde la source. Réponds à la question en te basant UNIQUEMENT sur ce que tu as réellement entendu ou vu. Pour l'audio/vidéo, cite des repères temporels (ex. "environ 02:30") quand c'est pertinent. Si la source ne contient pas de quoi répondre, dis-le explicitement — n'invente pas.
Écris la réponse à ce chemin ABSOLU : <WRITE_FILE>.
```

### MODE: doc-to-md
Timeout agy : `8m0s` (petit doc), `15m0s` si le header signale >20 pages via FOCUS. `--add-dir` : `<ADD_DIR>` (dossier source) ET `<CWD>`.
Prompt :
```
Tâche de conversion de document.
Fichier source : <SOURCE>
Type de fichier : <KIND>
Focus / à conserver : <FOCUS ou "conversion fidèle et intégrale">
Étapes :
1. Lis le fichier source avec tes outils fichier/multimodaux (selon le type).
2. Convertis en Markdown propre en préservant : hiérarchie des titres, tables (syntaxe markdown), listes (ordonnées/non), blocs de code, emphase (gras/italique).
3. Pour les images inline : insère un placeholder ![<meilleure description>](source-image-N), N séquentiel.
4. NE traduis PAS le contenu — garde la langue d'origine.
5. Ajoute un court frontmatter avec le chemin source, le type et la date de conversion.
Écris le markdown converti à ce chemin ABSOLU : <WRITE_FILE>.
```

## Règles de sécurité
- UN seul appel Bash pour l'invocation agy principale ; +1 appel pour le tri log et +1 pour le plan B, uniquement si le fichier est vide.
- Retourne la sortie/erreur d'agy verbatim. Ne paraphrase pas.
````

- [ ] **Step 2: Vérifier le frontmatter et la découverte**

Run: `head -6 ~/.claude/agents/agy-run.md`
Expected: frontmatter avec `name: agy-run`, `tools: Bash, Read`, `model: haiku`.

- [ ] **Step 3: Test e2e réel (le moins cher : doc-to-md sur un petit texte)**

```bash
cd "$(mktemp -d)" && printf '# Titre\n\nUn **paragraphe** et une liste :\n- a\n- b\n' > note.md
eval "$(python3 ~/.claude/scripts/agy/classify_source.py --mode doc-to-md --src note.md)"
echo "WRITE_FILE=$WRITE_FILE KIND=$KIND ADD_DIR=$ADD_DIR"
mkdir -p "$(dirname "$WRITE_FILE")"
agy --dangerously-skip-permissions --add-dir "$ADD_DIR" --add-dir "$PWD" \
  --model 'Gemini 3.5 Flash (High)' --print-timeout 8m0s \
  --print "Convertis le fichier $ADD_DIR/note.md en Markdown propre (garde la langue d'origine, préserve titres/listes/gras). Écris le résultat via write_file à ce chemin ABSOLU : $WRITE_FILE . N'imprime rien dans le chat, le fichier est ton seul livrable." < /dev/null
test -s "$WRITE_FILE" && echo "PASS: fichier écrit" && head -20 "$WRITE_FILE" || echo "FAIL: fichier absent/vide"
```
Expected: `PASS: fichier écrit`, contenu markdown non traduit. (Ce test valide le contrat d'invocation de bout en bout ; c'est le proxy exécutable du subagent, dont le corps markdown n'a pas de test unitaire.)

- [ ] **Step 4: Commit**

```bash
cd ~/.claude && git add agents/agy-run.md
git commit -m "feat(agy): subagent forwarder agy-run (modes multimodaux)"
```

---

### Task 3: Skill `/doc-to-md`

**Files:**
- Create: `~/.claude/skills/doc-to-md/SKILL.md`

**Interfaces:**
- Consumes: `classify_source.py` (Task 1), subagent `agy-run` mode doc-to-md (Task 2).

- [ ] **Step 1: Écrire la skill**

````markdown
---
name: doc-to-md
description: Convertit un PDF, docx, image ou HTML en Markdown propre via Antigravity (agy / Gemini multimodal) — tables, titres, listes préservés, langue d'origine conservée. Triggers : /doc-to-md, "convertis ce PDF/docx en markdown", "OCR ce document". Sauve dans docs/agy/converted/.
---

Convertit un document en Markdown en offloadant l'OCR/lecture multimodale vers `agy`.

Requête brute :
$ARGUMENTS

## Étape 1 — Résoudre la source (UN appel Bash)

Si `$ARGUMENTS` contient `--model <valeur>`, retire-le d'abord (ce n'est pas le focus) et garde `<valeur>` pour le header MODEL. Le premier token restant qui existe (`test -f`) est le fichier ; le reste est un focus optionnel. Aucun fichier valide → demande une fois « Quel fichier convertir ? » et stop.

```bash
python3 ~/.claude/scripts/agy/classify_source.py --mode doc-to-md --src "<FICHIER>"
mkdir -p docs/agy/converted
```

## Étape 2 — Déléguer à agy-run

Spawne UN subagent `agy-run` (Agent tool) avec ce header (FOCUS = le texte restant, ou vide) :

```
MODE: doc-to-md
KIND: <KIND de l'étape 1>
SOURCE: <chemin absolu du fichier>
ADD_DIR: <ADD_DIR de l'étape 1>
FOCUS: <focus ou vide>
MODEL: <valeur de --model si présente, sinon vide>
WRITE_FILE: <WRITE_FILE de l'étape 1>
CWD: <PWD absolu>
```

## Étape 3 — Présenter

Le subagent lit et retourne le fichier. Présente les ~30 premières lignes de la conversion puis le chemin sauvé. Ne retraite pas le document toi-même. Si agy-run remonte un souci binaire/auth, relaie son message verbatim (installation ou ré-auth).
````

- [ ] **Step 2: Test e2e réel**

Dans une session Claude Code avec la skill chargée : `/doc-to-md <un PDF réel court>`.
Expected: fichier `docs/agy/converted/<date>-<slug>.md` créé, non vide, tables/titres préservés, langue d'origine. Vérifier `test -s` sur le chemin annoncé.

- [ ] **Step 3: Commit**

```bash
cd ~/.claude && git add skills/doc-to-md/SKILL.md
git commit -m "feat(agy): skill /doc-to-md (document -> markdown via agy)"
```

---

### Task 4: Skill `/transcribe`

**Files:**
- Create: `~/.claude/skills/transcribe/SKILL.md`

**Interfaces:**
- Consumes: `classify_source.py` (Task 1), subagent `agy-run` mode transcribe (Task 2).

- [ ] **Step 1: Écrire la skill**

````markdown
---
name: transcribe
description: Transcrit et résume un fichier AUDIO ou VIDÉO (ou une URL YouTube/distante) via Antigravity (agy / Gemini multimodal) — ce que Claude Code ne sait pas faire nativement. Notes vocales, réunions, appels, screencasts. Transcript fidèle + résumé ; timestamps pour vidéo/URL. Triggers : /transcribe, "transcris cet audio/cette vidéo". Sauve dans docs/agy/transcripts/.
---

Offloade la compréhension audio/vidéo vers `agy` (Gemini est nativement multimodal ; Claude Code non).

Requête brute :
$ARGUMENTS

## Étape 1 — Résoudre source + kind (UN appel Bash)

Si `$ARGUMENTS` contient `--model <valeur>`, retire-le d'abord et garde `<valeur>` pour le header MODEL. Le premier token restant qui est une URL (`http(s)://`) OU un fichier existant (`test -f`) est la source ; le reste est un focus optionnel. Rien ne résout → demande une fois « Quel audio/vidéo/URL transcrire ? » et stop.

```bash
python3 ~/.claude/scripts/agy/classify_source.py --mode transcribe --src "<SOURCE>"
mkdir -p docs/agy/transcripts
```

## Étape 2 — Déléguer à agy-run

Spawne UN subagent `agy-run` avec :

```
MODE: transcribe
KIND: <KIND>
SOURCE: <chemin absolu ou URL>
ADD_DIR: <ADD_DIR (vide pour une URL)>
FOCUS: <focus ou vide>
MODEL: <valeur de --model si présente, sinon vide>
WRITE_FILE: <WRITE_FILE>
CWD: <PWD absolu>
```

## Étape 3 — Présenter

Lis ce que retourne le subagent : le résumé d'abord, puis le chemin du transcript. Ne retraite pas le média. Souci binaire/auth remonté par agy-run → relaie son message verbatim.

## Notes
- Formats audio (ogg/opus/mp3/wav/m4a/flac) et vidéo (mp4/mov/webm…) courants ; YouTube et URLs publiques marchent sans téléchargement.
- Fichiers > ~30 min : découper avec `ffmpeg` d'abord si timeout.
````

- [ ] **Step 2: Test e2e réel**

`/transcribe <un mp3 court réel>` puis `/transcribe <une URL YouTube publique courte>`.
Expected: `docs/agy/transcripts/<base>.md` créé, non vide ; timestamps présents pour l'URL ; langue = langue de la source (pas de traduction).

- [ ] **Step 3: Commit**

```bash
cd ~/.claude && git add skills/transcribe/SKILL.md
git commit -m "feat(agy): skill /transcribe (audio/video -> transcript via agy)"
```

---

### Task 5: Skill `/video`

**Files:**
- Create: `~/.claude/skills/video/SKILL.md`

**Interfaces:**
- Consumes: `classify_source.py` (Task 1), subagent `agy-run` mode video (Task 2).

- [ ] **Step 1: Écrire la skill**

````markdown
---
name: video
description: REGARDE une vidéo et renvoie un breakdown VISUEL structuré (pas juste un transcript) via Antigravity (agy / Gemini multimodal vidéo) — scènes horodatées, texte à l'écran/OCR (slides, graphiques, UI), moments clés. Pour screencasts, tutos, démos, présentations, inspections. Triggers : /video, "analyse cette vidéo", "que montre cette vidéo". Sauve dans docs/agy/video/.
---

Donne des yeux à Claude sur une vidéo : `agy` la REGARDE et renvoie un breakdown visuel horodaté (ce qui est montré, pas seulement dit). Pour un transcript pur, `/transcribe` ; pour une question ciblée, `/media`.

Requête brute :
$ARGUMENTS

## Étape 1 — Résoudre source + kind (UN appel Bash)

Si `$ARGUMENTS` contient `--model <valeur>`, retire-le d'abord et garde `<valeur>` pour le header MODEL. Premier token restant URL ou fichier existant = source ; reste = focus. Rien → demande une fois « Quelle vidéo analyser (fichier ou URL) ? » et stop.

```bash
python3 ~/.claude/scripts/agy/classify_source.py --mode video --src "<SOURCE>"
mkdir -p docs/agy/video
```

## Étape 2 — Déléguer à agy-run

```
MODE: video
KIND: <KIND>
SOURCE: <chemin absolu ou URL>
ADD_DIR: <ADD_DIR (vide pour une URL)>
FOCUS: <focus ou vide>
MODEL: <valeur de --model si présente, sinon vide>
WRITE_FILE: <WRITE_FILE>
CWD: <PWD absolu>
```

## Étape 3 — Présenter

Présente le résumé d'abord, puis la table des scènes, puis le chemin sauvé. Ne retraite pas la vidéo. Souci binaire/auth remonté par agy-run → relaie son message verbatim.

## Notes
- Sortie = breakdown visuel : `## Résumé`, table `## Scènes`, `## Texte à l'écran`, `## Moments clés`.
- Vidéos > ~15 min : peuvent timeouter (agy-run monte le timeout à 12 min) ; découper avec `ffmpeg` si besoin.
````

- [ ] **Step 2: Test e2e réel**

`/video <un mp4 court réel avec du texte à l'écran>`.
Expected: `docs/agy/video/<base>.md` créé ; sections `## Résumé`, `## Scènes` (table), `## Texte à l'écran`, `## Moments clés` présentes et en français ; OCR du texte à l'écran présent.

- [ ] **Step 3: Commit**

```bash
cd ~/.claude && git add skills/video/SKILL.md
git commit -m "feat(agy): skill /video (breakdown visuel via agy)"
```

---

### Task 6: Skill `/media`

**Files:**
- Create: `~/.claude/skills/media/SKILL.md`

**Interfaces:**
- Consumes: `classify_source.py` (Task 1), subagent `agy-run` mode media (Task 2).

- [ ] **Step 1: Écrire la skill**

````markdown
---
name: media
description: Pose une question sur un fichier AUDIO, VIDÉO ou IMAGE (ou une URL YouTube/distante) via Antigravity (agy / Gemini multimodal). Au-delà de la transcription — "quelles décisions ont été prises ?", "que se passe-t-il à 2:30 ?", "quel est le ton de cette note vocale ?". Claude Code ne voit/n'entend pas les médias ; agy si. Triggers : /media, "demande à la vidéo/l'audio", "que dit cette image". Sauve dans docs/agy/media/.
---

Question-réponse multimodale sur un média : `agy` répond en se basant sur ce qu'il a entendu/vu, avec repères temporels pour audio/vidéo.

Requête brute :
$ARGUMENTS

## Étape 1 — Résoudre source + question (UN appel Bash)

Si `$ARGUMENTS` contient `--model <valeur>`, retire-le d'abord et garde `<valeur>` pour le header MODEL. Sépare le reste sur le premier `|` → gauche = source (URL ou fichier existant), droite = question. Sans `|`, le token URL/fichier en tête est la source, le reste la question. Question vide → demande une fois et stop.

```bash
python3 ~/.claude/scripts/agy/classify_source.py --mode media --src "<SOURCE>" --question "<QUESTION>"
mkdir -p docs/agy/media
```

## Étape 2 — Déléguer à agy-run

```
MODE: media
KIND: <KIND>
SOURCE: <chemin absolu ou URL>
ADD_DIR: <ADD_DIR (vide pour une URL)>
QUESTION: <question>
MODEL: <valeur de --model si présente, sinon vide>
WRITE_FILE: <WRITE_FILE>
CWD: <PWD absolu>
```

## Étape 3 — Présenter

Présente la réponse verbatim puis le chemin sauvé. Ne retraite pas le média. Souci binaire/auth remonté par agy-run → relaie son message verbatim.

## Notes
- Pour audio/vidéo, la réponse cite des repères temporels (ex. "environ 02:30").
- Transcript complet plutôt qu'une réponse ciblée ? → `/transcribe`.
````

- [ ] **Step 2: Test e2e réel**

`/media <un mp4 court> | que se passe-t-il vers le début ?` et `/media <une image> | que montre cette image ?`.
Expected: `docs/agy/media/<base>-<hash>.md` créé, réponse en français, repère temporel présent pour la vidéo.

- [ ] **Step 3: Commit**

```bash
cd ~/.claude && git add skills/media/SKILL.md
git commit -m "feat(agy): skill /media (Q&A multimodal via agy)"
```

---

## Phase 2 — Deep research

### Task 7: Lib de rendu `deep-agy-lib.mjs` + CLI + tests

**Files:**
- Create: `~/.claude/scripts/agy/deep-agy-lib.mjs` (copie de la source + en-têtes de rendu FR)
- Create: `~/.claude/scripts/agy/render-report.mjs` (copie + import renommé)
- Test: `~/.claude/scripts/agy/tests/deep-agy-lib.test.mjs`

**Interfaces:**
- Produces: exports `normURL, domainOf, distinctDomains, corroborationOf, ingestRound, isConverged, computeCoverage, rankClaimsForRedTeam, applyRedTeam, renderReportMarkdown`. Signatures identiques à la source `deep-research-lib.mjs`.

- [ ] **Step 1: Copier la lib source puis franciser le rendu**

```bash
mkdir -p ~/.claude/scripts/agy/tests
cp ~/dev/antigravity-plugin-cc-main/plugins/antigravity/scripts/deep-research-lib.mjs ~/.claude/scripts/agy/deep-agy-lib.mjs
cp ~/dev/antigravity-plugin-cc-main/plugins/antigravity/scripts/render-report.mjs ~/.claude/scripts/agy/render-report.mjs
# render-report.mjs importe l'ancien nom de lib → le renommer vers la copie locale
sed -i '' "s|'./deep-research-lib.mjs'|'./deep-agy-lib.mjs'|" ~/.claude/scripts/agy/render-report.mjs
```

Puis dans `deep-agy-lib.mjs`, remplacer UNIQUEMENT dans la fonction `renderReportMarkdown` les chaînes espagnoles par leur équivalent français (le reste du fichier — helpers de calcul — reste identique à la source, c'est ce que le test de sync de la Task 8 vérifie) :

| Source (es) | Cible (fr) |
|---|---|
| `{ evidence:'EVIDENCIA', inference:'INFERENCIA', assumption:'SUPUESTO' }` | `{ evidence:'PREUVE', inference:'INFÉRENCE', assumption:'HYPOTHÈSE' }` |
| `'## Contexto'` | `'## Contexte'` |
| `'## Comparaciones'` | `'## Comparaisons'` |
| `'## Riesgos y contraargumentos'` | `'## Risques et contre-arguments'` |
| `'## Recomendación aplicada'` | `'## Recommandation appliquée'` |
| `` `**Por qué:** ${a.rationale}\n` `` | `` `**Pourquoi :** ${a.rationale}\n` `` |
| `` `**Contexto local:** ${a.groundedContext}\n` `` | `` `**Contexte local :** ${a.groundedContext}\n` `` |
| `'## Evidence gaps'` | `'## Lacunes de preuve'` |
| `'## Cobertura y confianza'` | `'## Couverture et confiance'` |
| `` `- Ángulos completados: ${...} · caídos: ${...}...` `` | `` `- Angles complétés : ${...} · échoués : ${...}...` `` |
| `` `- Fuentes: ${...} · dominios distintos: ${...}` `` | `` `- Sources : ${...} · domaines distincts : ${...}` `` |
| `'- Gaps críticos sin resolver:'` | `'- Lacunes critiques non résolues :'` |
| `'- Penalizaciones de confianza:'` | `'- Pénalités de confiance :'` |
| `'## Conclusión'` | `'## Conclusion'` |
| `` `**Confianza global:** ${...}` `` | `` `**Confiance globale :** ${...}` `` |
| `'## Referencias'` | `'## Références'` |

(Rendu FR déjà validé sous bun le 2026-07-17 : frontmatter + en-têtes FR + tags FR, zéro résidu espagnol.)

- [ ] **Step 2: Écrire le test de la lib**

```javascript
// ~/.claude/scripts/agy/tests/deep-agy-lib.test.mjs
import { test, expect } from 'bun:test'
import { normURL, corroborationOf, ingestRound, rankClaimsForRedTeam, applyRedTeam, renderReportMarkdown } from '../deep-agy-lib.mjs'

test('normURL strips www and trailing slash, lowercases', () => {
  expect(normURL('https://www.Example.com/Path/')).toBe('example.com/path')
})

test('corroborationOf: >=2 distinct domains = independent', () => {
  expect(corroborationOf({ sources: ['https://a.com/1', 'https://b.com/2'] })).toBe('independent')
  expect(corroborationOf({ sources: ['https://a.com/1', 'https://a.com/2'] })).toBe('single-source')
})

test('ingestRound dedups by primary url + claim prefix', () => {
  const state = { findings: [], seenKeys: new Set(), failedAngles: [] }
  const round = [{ angle: 'x', status: 'ok', findings: [
    { claim: 'C1', sources: ['https://a.com'], sourceQuality: 'primary', importance: 'central' },
    { claim: 'C1', sources: ['https://a.com'], sourceQuality: 'primary', importance: 'central' },
  ]}]
  expect(ingestRound(round, state, 1)).toBe(1)
  expect(state.findings.length).toBe(1)
  expect(state.findings[0].confidence).toBe('high')
})

test('ingestRound records failed angles', () => {
  const state = { findings: [], seenKeys: new Set(), failedAngles: [] }
  ingestRound([{ angle: 'dead', status: 'failed' }], state, 1)
  expect(state.failedAngles).toEqual(['dead'])
})

test('rankClaimsForRedTeam keeps central/single-source, respects limit', () => {
  const findings = [
    { claim: 'a', importance: 'central', corroboration: 'independent' },
    { claim: 'b', importance: 'tangential', corroboration: 'single-source' },
    { claim: 'c', importance: 'supporting', corroboration: 'independent' },
  ]
  const r = rankClaimsForRedTeam(findings, 5)
  expect(r.map(f => f.claim).sort()).toEqual(['a', 'b'])
})

test('applyRedTeam kills, downgrades, holds', () => {
  const findings = [
    { claim: 'k', confidence: 'high' }, { claim: 'd', confidence: 'high' }, { claim: 'h', confidence: 'high' },
  ]
  const verdicts = [
    { claim: 'k', verdict: 'kill' },
    { claim: 'd', verdict: 'downgrade', newConfidence: 'low' },
    { claim: 'h', verdict: 'hold' },
  ]
  const r = applyRedTeam(findings, verdicts)
  expect(r.map(f => f.claim)).toEqual(['d', 'h'])
  expect(r.find(f => f.claim === 'd').confidence).toBe('low')
})

test('renderReportMarkdown emits French scaffolding, no Spanish', () => {
  const md = renderReportMarkdown(
    { tldr: ['x'], findings: [{ statement: 'S', type: 'evidence', confidence: 'high', sources: ['https://a.com'] }],
      coverage: { anglesCompleted: 1, anglesFailed: 0 }, conclusion: { recommendation: 'R', overallConfidence: 'high' }, references: [] },
    { title: 'T', depth: 'L', rounds: 1, converged: true, date: '2026-07-17' })
  expect(md.startsWith('---\ntitle: "T"')).toBe(true)
  expect(md).toContain('## Couverture et confiance')
  expect(md).toContain('[PREUVE · high]')
  expect(md).not.toMatch(/## (Contexto|Conclusión|Referencias|Cobertura)/)
})
```

- [ ] **Step 3: Lancer les tests**

Run: `cd ~/.claude/scripts/agy && bun test tests/deep-agy-lib.test.mjs`
Expected: 7 pass, 0 fail.

- [ ] **Step 4: Commit**

```bash
cd ~/.claude && git add scripts/agy/deep-agy-lib.mjs scripts/agy/render-report.mjs scripts/agy/tests/deep-agy-lib.test.mjs
git commit -m "feat(agy): lib de rendu deep-research (rendu FR) + CLI + tests"
```

---

### Task 8: Workflow `deep-agy.js` + test de sync

**Files:**
- Create: `~/.claude/scripts/agy/deep-agy.js` (copie de la source, helpers inline + agentType agy-run)
- Test: `~/.claude/scripts/agy/tests/deep-agy-sync.test.mjs`

**Interfaces:**
- Consumes: `agy-run` modes deep-angle/redteam (Task 10, câblés via `agentType:'agy-run'`), lib helpers (Task 7, inlinés verbatim).
- Produces: Workflow retournant `{ report, coverage, rounds, converged }`. `args` objet `{ question, matrix, angles, depth, engines, deepDir, date, title }`.

- [ ] **Step 1: Copier le workflow source et le réécrire**

```bash
cp ~/dev/antigravity-plugin-cc-main/plugins/antigravity/scripts/deep-research-agy.js ~/.claude/scripts/agy/deep-agy.js
```

Appliquer exactement ces trois éditions dans `deep-agy.js` :
1. Bloc `meta` (lignes 1-3) → remplacer `name: 'deep-research-agy'` par `name: 'deep-agy'`. Laisser `description` et `phases` tels quels.
2. Les DEUX occurrences de `agentType:'antigravity:agy-rescue'` → `agentType:'agy-run'` (une dans la boucle d'angles, une dans le red-team).
3. Rien d'autre. Le bloc `// ─── INLINED from deep-research-lib.mjs ───ok ... // ─── END INLINED ───` reste identique à la source (c'est le contrat vérifié par le test de sync).

- [ ] **Step 2: Écrire le test de sync inline/lib**

```javascript
// ~/.claude/scripts/agy/tests/deep-agy-sync.test.mjs
// Garde-fou : les helpers inlinés dans deep-agy.js doivent rester identiques
// à deep-agy-lib.mjs (les scripts Workflow ne peuvent pas importer de fichier local).
import { test, expect } from 'bun:test'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const here = dirname(fileURLToPath(import.meta.url))
const wf = readFileSync(join(here, '..', 'deep-agy.js'), 'utf8')
const lib = readFileSync(join(here, '..', 'deep-agy-lib.mjs'), 'utf8')

// Extrait le corps d'une fonction nommée `function NAME(...) { ... }` (accolades équilibrées).
function extractFn(src, name) {
  const start = src.indexOf(`function ${name}(`)
  if (start === -1) return null
  let i = src.indexOf('{', start), depth = 0
  for (let j = i; j < src.length; j++) {
    if (src[j] === '{') depth++
    else if (src[j] === '}') { depth--; if (depth === 0) return src.slice(start, j + 1) }
  }
  return null
}

// Helpers de calcul partagés (renderReportMarkdown n'est PAS inliné dans le workflow).
const SHARED = ['normURL', 'domainOf', 'distinctDomains', 'corroborationOf',
  'initialConfidence', 'ingestRound', 'isConverged', 'computeCoverage',
  'rankClaimsForRedTeam', 'applyRedTeam']

for (const name of SHARED) {
  test(`inline ${name} matches lib`, () => {
    const inWf = extractFn(wf, name)
    const inLib = extractFn(lib.replace(/\bexport function /g, 'function '), name)
    expect(inWf).not.toBeNull()
    expect(inLib).not.toBeNull()
    expect(inWf).toBe(inLib)
  })
}

test('deep-agy.js targets the agy-run subagent, not agy-rescue', () => {
  expect(wf).not.toContain('antigravity:agy-rescue')
  expect(wf).toMatch(/agentType:\s*'agy-run'/)
})
```

- [ ] **Step 3: Lancer le test**

Run: `cd ~/.claude/scripts/agy && bun test tests/deep-agy-sync.test.mjs`
Expected: 11 pass (10 helpers identiques + le check agentType). Si un helper diffère, re-copier le bloc INLINED depuis `deep-agy-lib.mjs` (en retirant `export `).

- [ ] **Step 4: Commit**

```bash
cd ~/.claude && git add scripts/agy/deep-agy.js scripts/agy/tests/deep-agy-sync.test.mjs
git commit -m "feat(agy): workflow deep-agy (agentType agy-run) + test de sync"
```

---

### Task 9: Copier `agy_scratch.py`

**Files:**
- Create: `~/.claude/scripts/agy/agy_scratch.py` (copie verbatim, repo-indépendant)

**Interfaces:**
- Produces: CLI `python3 agy_scratch.py --timeout N --in ABS --out ABS --prompt "..."` qui stage inputs+outputs en scratch, lance agy `--add-dir <scratch>`, déplace les `--out` vers leur chemin final, imprime `MOVED`/`MISSING`.

- [ ] **Step 1: Copier le script**

```bash
cp ~/dev/antigravity-plugin-cc-main/plugins/antigravity/scripts/agy_scratch.py ~/.claude/scripts/agy/agy_scratch.py
```
Aucune édition : le script résout le binaire agy lui-même et n'a aucune dépendance au repo. (macOS : le fallback Windows `~/AppData/...` est mort-code inoffensif, on le laisse pour rester byte-identique à la source.)

- [ ] **Step 2: Smoke test (staging + move, sans dépendre du modèle)**

```bash
cd "$(mktemp -d)" && printf 'bonjour' > in.txt
python3 ~/.claude/scripts/agy/agy_scratch.py --timeout 30 --in "$PWD/in.txt" --out "$PWD/out.txt" \
  --prompt "Copie le contenu de $PWD/in.txt dans le fichier $PWD/out.txt via write_file, rien d'autre." 2>&1 | tail -2
echo "exists=$([ -s "$PWD/out.txt" ] && echo yes || echo no)"
```
Expected: ligne `MOVED <...>/out.txt` et `exists=yes` (valide le staging + move réel end-to-end via agy).

- [ ] **Step 3: Commit**

```bash
cd ~/.claude && git add scripts/agy/agy_scratch.py
git commit -m "feat(agy): scratch-then-move runner agy_scratch.py (copie MIT)"
```

---

### Task 10: Ajouter les modes `deep-angle` + `redteam` à `agy-run`

**Files:**
- Modify: `~/.claude/agents/agy-run.md` (ajouter deux modes après les modes multimodaux)

**Interfaces:**
- Consumes: `agy_scratch.py` (Task 9).
- Produces: mode `deep-angle` (écrit un markdown de claims via scratch, le Workflow le structure en ANGLE_SCHEMA) ; mode `redteam` (écrit un JSON de verdict via scratch, structuré en REDTEAM_SCHEMA). Le Workflow (Task 8) les appelle avec `schema:` — la structuration est guidée par la couche Workflow.

- [ ] **Step 1: Ajouter les deux modes**

Dans `~/.claude/agents/agy-run.md`, après le mode `doc-to-md` et avant `## Règles de sécurité`, insérer :

````markdown
### MODE: deep-angle
Un angle d'une investigation deep-research (orchestré par le Workflow deep-agy). Browsing étroit et profond. Header : QUERY, QUESTION, ROUND, TIMEOUT, WRITE_FILE. Le TIMEOUT du header est une durée Go (`3m0s` défaut L, `4m0s` H) ; `agy_scratch.py --timeout` attend des SECONDES ENTIÈRES — convertis donc `3m0s`→`180`, `4m0s`→`240` (ne jamais dépasser 480). Fixe le timeout de l'outil Bash à ces secondes + 60.
Invoque via le scratch runner (écrire dans deepDir, à l'intérieur du projet, sans snapshotter tout le repo) :
```bash
python3 ~/.claude/scripts/agy/agy_scratch.py --timeout <secondes entières : 180 pour 3m0s, 240 pour 4m0s> --out "<WRITE_FILE>" --prompt "<PROMPT ci-dessous>"
```
Prompt :
```
Tu es UN angle d'une investigation de recherche plus large. Va étroit et profond.
Question globale : <QUESTION>
Ton angle : <QUERY>
Règles :
- Fais une recherche web sur l'angle. Renvoie 4-8 claims FALSIFIABLES portant sur la question globale.
- Chaque claim : une affirmation vérifiable concrète + une citation d'appui directe + la/les URL(s) source + la qualité de source (primary|secondary|blog|forum|unreliable) + la récence (YYYY-MM-DD ou "unknown").
- Privilégie les sources primaires. Ignore le spam SEO / fermes de contenu.
- Termine par THREADS TO PULL : les pistes riches à creuser. Classe CHACUNE en decision-critical | contradiction-risk | recency-risk | nice-to-have. N'invente pas de threads pour remplir — si aucune, dis-le.
- Langue de sortie : celle de la question (défaut français).
Écris le markdown complet (claims + citations + sources + THREADS TO PULL) via write_file à : <WRITE_FILE>. Après écriture, confirme le chemin. C'est ton seul livrable.
```
Après le run : `Read` `<WRITE_FILE>` et retourne son contenu (le Workflow le structure en ANGLE_SCHEMA). Fichier absent après plan B → retourne un marqueur d'échec `status: failed` pour cet angle.

### MODE: redteam
Attaque UN claim en cherchant à le réfuter (orchestré par deep-agy). Header : CLAIM, QUESTION, WRITE_FILE. Timeout : `180` secondes (3m0s). Même invocation scratch runner que deep-angle, en secondes entières : `python3 ~/.claude/scripts/agy/agy_scratch.py --timeout 180 --out "<WRITE_FILE>" --prompt "<le prompt ci-dessous>"` ; fixe le timeout de l'outil Bash à 180 + 60.
Prompt :
```
Red-team adversarial. Sois SCEPTIQUE — cherche à RÉFUTER ce claim.
Question de recherche : <QUESTION>
Claim attaqué : "<CLAIM>"
Checklist :
1. Recherche web de preuves contradictoires — une source crédible le conteste/le nuance fortement ?
2. La qualité de source suffit-elle à la force du claim ? (un claim extraordinaire exige des sources primaires)
3. Est-il périmé ? (domaines qui bougent vite — un vieux claim est suspect)
4. Est-ce du marketing / communiqué / benchmark cherry-pické / spéculation de forum ?
Verdict : kill (non étayé/contredit/marketing) | downgrade (partiellement vrai, plus faible qu'énoncé) | hold (bien étayé, actuel, source à la hauteur). Par défaut downgrade/kill si incertain.
Écris un objet JSON conforme à {claim, refuted, refutingEvidence, refutingSource, recencyOk, verdict, newConfidence} via write_file à <WRITE_FILE>. Confirme le chemin. Seul livrable.
```
Après le run : `Read` `<WRITE_FILE>` et retourne le JSON (structuré en REDTEAM_SCHEMA par le Workflow). Absent après plan B → `{ claim, refuted:false, verdict:'hold', recencyOk:true }` (fail-open : une panne infra ne tue pas un claim).
````

- [ ] **Step 2: Vérifier la présence des deux modes**

Run: `grep -c '^### MODE:' ~/.claude/agents/agy-run.md`
Expected: `6`.

- [ ] **Step 3: Commit**

```bash
cd ~/.claude && git add agents/agy-run.md
git commit -m "feat(agy): agy-run modes deep-angle + redteam (via scratch runner)"
```

---

### Task 11: Skill `/agy-deep`

**Files:**
- Create: `~/.claude/skills/agy-deep/SKILL.md`

**Interfaces:**
- Consumes: Workflow `deep-agy.js` (Task 8), lib `render-report.mjs` (Task 7), subagent `agy-run` deep-angle/redteam (Task 10).

- [ ] **Step 1: Écrire la skill**

````markdown
---
name: agy-deep
description: Deep research multi-rounds via agy (browsing Gemini groundé Google) — matrice de preuves + plan que tu valides, angles browsés en parallèle, analyse de convergence, passe red-team, rapport cité avec tags preuve/inférence/hypothèse et recommandation appliquée. Pour les décisions lourdes où la justesse prime sur la vitesse. Complémentaire de search-deep (qui reste la voie recherche rapide). Triggers : /agy-deep, "deep research approfondie", "recherche multi-rounds". Sauve dans docs/agy/research/.
allowed-tools: Bash, Write, Read, Workflow, Agent
---

Deep research multi-rounds. Ne remplace pas `search-deep` (rapide, un coup) : ici on boucle via le Workflow `deep-agy` — agy browse plusieurs angles par round, Claude juge couverture et convergence entre rounds, une passe red-team attaque les claims centraux/mono-source, puis synthèse.

> Cette skill AUTORISE explicitement l'appel du tool `Workflow` (opt-in par instruction de skill). Le Workflow spawne un subagent `agy-run` par angle/claim.

Requête brute :
$ARGUMENTS

## Étape 1 — Parse + préflight (UN appel Bash)

- `--depth L|H` (défaut `L`). `H` = jusqu'à 4 rounds (vs 2), red-team 10 claims (vs 5), timeouts par angle plus longs.
- `--yes` saute le plan gate (Étape 3).
- Retire ces flags de `$ARGUMENTS` ; le reste trimé = `<sujet>`. Vide → demande « Quoi deep-rechercher ? » et stop.
- `SLUG` = sujet lowercased, non-alphanumérique → `-`, répétitions réduites, 60 chars. `DATE` = aujourd'hui ISO.
- Chemins ABSOLUS obligatoires : le Workflow et ses subagents tournent dans un cwd différent, et un `~` ou un chemin relatif passé en argument de tool (`scriptPath`, `deepDir`) n'est PAS expansé. Le préflight ci-dessous résout et imprime `SCRIPT`, `RENDER`, `WRITE_FILE`, `DEEP_DIR` — réutilise ces valeurs littérales telles quelles aux Étapes 4-5.

```bash
mkdir -p "docs/agy/research/.deep/<DATE>-<SLUG>"
echo "SCRIPT=$HOME/.claude/scripts/agy/deep-agy.js"
echo "RENDER=$HOME/.claude/scripts/agy/render-report.mjs"
echo "WRITE_FILE=$(pwd)/docs/agy/research/<DATE>-<SLUG>.md"
echo "DEEP_DIR=$(pwd)/docs/agy/research/.deep/<DATE>-<SLUG>"
command -v agy >/dev/null 2>&1 && agy --version || echo "AGY_MISSING"
```
`AGY_MISSING` → dire à l'utilisateur d'installer agy (https://antigravity.google) ou de lancer `agy` une fois en terminal pour l'OAuth, puis STOP (ne pas lancer un Workflow multi-rounds contre un agy mort).

## Étape 2 — Matrice de preuves + angles (Claude raisonne, sans tool)

Décompose `<sujet>` en :
1. **Matrice** : lignes `{ id, question, evidenceType, sourceQualityBar, recencyRequirement, contradictionCheck, recommendationChanging }`. `recommendationChanging: true` marque les lignes qui pourraient renverser la conclusion.
2. **Angles** : `{ label, query, rationale, targetsMatrixIds }`. 3-4 angles en `L`, 5-6 en `H`. Chaque angle cible ≥1 ligne ; chaque ligne recommendationChanging est ciblée par ≥1 angle.

## Étape 3 — Plan gate (sauté si `--yes`)

Montre la matrice + les angles (table compacte) et attends un go explicite ou des edits. Applique les edits puis re-montre si non triviaux. Avec `--yes`, saute cette étape.

## Étape 4 — Lancer le Workflow

```
Workflow({
  scriptPath: "<SCRIPT résolu à l'Étape 1 — chemin absolu, jamais ~>",
  args: { question: <sujet>, matrix: <matrice>, angles: <angles>, depth: "L"|"H",
          engines: "agy", deepDir: "<DEEP_DIR résolu à l'Étape 1 — absolu>", date: <DATE>, title: <sujet> }
})
```
Attends le résultat `{ report, coverage, rounds, converged }`. `report` est déjà au schéma et `report.coverage` est pré-calculé (déterministe) — ne pas recomputer.

## Étape 5 — Rendu (Claude, après le Workflow)

N'écris pas le markdown à la main. Écris `{ report, meta }` dans `<DEEP_DIR>/_render.json` (Write) puis rends via le CLI (UN Bash) :
```bash
node "<RENDER résolu à l'Étape 1>" "<DEEP_DIR résolu>/_render.json" > "<WRITE_FILE résolu>"
```
où `meta = { title:<sujet>, depth:<L|H>, rounds:<result.rounds>, converged:<result.converged>, date:<DATE> }`.
(`render-report.mjs` importe la lib en spécifieur relatif — ne jamais inliner le chemin de la lib dans un `node -e`.)

## Étape 6 — Retour

Retourne le chemin `WRITE_FILE` + les ~30 premières lignes du fichier rendu (TL;DR + Couverture). Verbatim, ne paraphrase pas.

## Notes
- Cette skill ne parle jamais à agy directement : chaque appel agy se fait dans le Workflow, un subagent `agy-run` par angle/claim. Un agy cassé en cours → l'angle revient `failed`, la couverture se dégrade (notée dans `coverage.failedAngleLabels`) sans crasher le run.
- `search-deep` reste la voie rapide au quotidien ; réserve `/agy-deep` aux décisions où la justesse prime.
````

- [ ] **Step 2: Vérifier que node résout la lib depuis le CLI**

```bash
cd "$(mktemp -d)" && cat > r.json <<'JSON'
{"report":{"tldr":["ok"],"findings":[],"coverage":{"anglesCompleted":1,"anglesFailed":0},"conclusion":{"recommendation":"R","overallConfidence":"high"},"references":[]},"meta":{"title":"T","depth":"L","rounds":1,"converged":true,"date":"2026-07-17"}}
JSON
node ~/.claude/scripts/agy/render-report.mjs r.json | head -3
```
Expected: les 3 premières lignes du frontmatter (`---`, `title: "T"`, `type: research`).

- [ ] **Step 3: Test e2e réel du chemin complet**

Dans une session Claude Code : `/agy-deep un sujet bateau vérifiable --depth L --yes`.
Expected: le Workflow tourne (rounds visibles), `docs/agy/research/<date>-<slug>.md` créé avec frontmatter FR, sections TL;DR + Couverture et confiance ; artefacts bruts dans `.deep/<date>-<slug>/`. Vérifier `test -s` sur le chemin annoncé.

- [ ] **Step 4: Commit**

```bash
cd ~/.claude && git add skills/agy-deep/SKILL.md
git commit -m "feat(agy): skill /agy-deep (deep research multi-rounds via Workflow)"
```

---

## Vérification finale (après toutes les tâches)

Échantillon réel par mode, dans un dossier de test jetable :
- [ ] `/transcribe <mp3 court>` → transcript FR/langue source, `test -s` OK.
- [ ] `/transcribe <URL YouTube publique>` → timestamps présents.
- [ ] `/video <mp4 court avec texte à l'écran>` → 4 sections FR + OCR.
- [ ] `/media <mp4> | question` → réponse FR + repère temporel.
- [ ] `/doc-to-md <PDF scanné>` → markdown, langue d'origine, tables préservées.
- [ ] `/agy-deep <sujet> --depth L --yes` → rapport cité FR + couverture.
- [ ] Plan B exercé une fois : lancer un mode avec un WRITE_FILE volontairement non-inscriptible et vérifier que agy-run récupère depuis le transcript ou remonte un échec verbeux (pas un vide silencieux).
- [ ] `cd ~/.claude/scripts/agy && bun test && python3 tests/test_classify_source.py` → tout vert.

## Couverture spec → tâches

| Exigence spec | Tâche(s) |
|---|---|
| Agent forwarder agy-run, 6 modes, haiku | 2 (multimodal), 10 (deep-angle/redteam) |
| Skills /transcribe /video /media /doc-to-md | 4, 5, 6, 3 |
| Skill /agy-deep (Workflow) | 11 |
| classify_source.py (dédup heredocs) | 1 |
| agy_scratch.py (copie) | 9 |
| deep-agy.js + lib + render + sync test | 7, 8 |
| Sorties docs/agy/<kind>/ | 1 (chemins), chaque skill (mkdir) |
| Langue FR par défaut | 2 (prompts), 7 (rendu), 10 (prompts) |
| Contrat d'invocation durci (< /dev/null, --print last, timeout+60s) | 2 (agy-run), Global Constraints |
| Modèle Flash (High) via flag | 2 (agy-run MODEL + table d'alias), Global Constraints |
| Override --model par skill | 3,4,5,6 (headers MODEL) ; /agy-deep exclu (déviation assumée, Global Constraints) |
| Gestion erreurs (préflight, plan B, auth-timeout) | 2 (agy-run), 11 (préflight) |
| macOS only (pas de Windows) | Global Constraints |
| NotebookLM exclu | (aucune tâche — hors périmètre) |
| search-deep inchangé | (aucune tâche — laissé tel quel) |
````
