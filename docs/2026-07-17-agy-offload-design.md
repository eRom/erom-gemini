# Design — agy-offload

Date : 2026-07-17. Statut : validé par Romain (sections 1 et 2 approuvées en brainstorm).
Chantier : offloader vers Antigravity CLI (`agy`, Gemini, Google AI Pro) les capacités où Claude Code est faible ou coûteux.

## Contexte et objectif

Le repo opensource `antigravity-plugin-cc` (MarcosNahuel, MIT, copie analysée dans `~/dev/antigravity-plugin-cc-main`, plugin v1.5.1) fournit un pont Claude Code → `agy` éprouvé. Décision : **pas de fork GitHub** ; on extrait prompts, patterns et scripts, réécrits dans l'idiome du harnais de Romain, dans `~/.claude` (repo git existant, branche main).

Objectifs :
- Donner à Claude Code des oreilles et des yeux (audio, vidéo, OCR documents) via Gemini multimodal.
- Ajouter un deep-research multi-rounds rigoureux (matrice de preuves, red-team, convergence) pour les décisions lourdes.
- Déplacer les coûts tokens vers l'abonnement Google AI Pro.

## Périmètre

**In** : transcribe, video, media, doc-to-md (multimodal) ; deep-research multi-rounds (workflow).
**Out** : tout NotebookLM (notebook*), report HTML, record, scrape, design-review, rescue, review, second avis multi-provider pour les devils. `search-deep` existant **inchangé** : il reste la voie recherche quotidienne (skill `/cowork:deep-research` côté agy) ; le deep du fork le complète pour les décisions lourdes, sans le remplacer.

## Architecture

Tout vit dans `~/.claude` (versionné git). Aucun repo séparé, aucun format plugin.

### Agent forwarder : `agents/agy-run.md`

Pendant réduit d'`agy-rescue` (source : `plugins/antigravity/agents/agy-rescue.md` du repo). 6 modes : `transcribe`, `video`, `media`, `doc-to-md`, `deep-angle`, `redteam`.

- `tools: Bash, Read` ; `model: haiku` (pure plomberie : parser un header, un appel Bash, lire un fichier).
- Description à l'idiome maison : « réservé aux skills agy-*, ne pas utiliser pour déléguer librement ».
- Header d'entrée (inspiré du repo) :

```
MODE: transcribe|video|media|doc-to-md|deep-angle|redteam
KIND: audio|video|image|url|file        # selon mode
SOURCE: <chemin ou URL>
ADD_DIR: <dossier du fichier source, vide pour URL>
FOCUS: <texte ou vide>                   # transcribe/video/doc-to-md
PREGUNTA→QUESTION: <question>            # media (renommé QUESTION)
QUERY / ROUND / CLAIM: …                 # deep-angle / redteam
MODEL: <label exact agy models, vide = défaut>
WRITE_FILE: <chemin absolu>
CWD: <chemin absolu>
```

- Prompts par mode : adaptés depuis `agy-rescue.md` (transcribe l.792-819, media l.821-843, video l.845-880, doc-to-md l.542-578, deep-angle l.1163-1190, redteam l.1192-1217), traduits (voir Langue).

### Skills user-invocables : `skills/`

| Skill | Arguments | Rôle |
|---|---|---|
| `/transcribe` | `<fichier\|URL> [focus]` | transcript fidèle + résumé, timestamps vidéo/URL |
| `/video` | `<fichier\|URL> [focus]` | breakdown VISUEL : scènes, OCR écran, moments clés |
| `/media` | `<fichier\|URL> \| <question>` | Q&A multimodal ciblé, références temporelles |
| `/doc-to-md` | `<fichier> [focus]` | PDF/docx/image/HTML → markdown propre |
| `/agy-deep` | `<sujet> [--depth L\|H] [--yes]` | deep-research multi-rounds via Workflow |

Chaque skill multimodale : classifie la source (`classify_source.py`), calcule WRITE_FILE, spawne `agy-run`, présente résumé puis chemin, sans retraiter le média.

Nommage : `/agy-deep` (et pas `/deep-research`) car une skill `deep-research` existe déjà (harnais websearch côté Claude). Les deux coexistent : moteurs différents (fan-out Claude vs browsing Gemini offloadé). Fusion éventuelle hors scope.

### Scripts partagés : `scripts/agy/`

- `agy_scratch.py` : copié tel quel du repo (`plugins/antigravity/scripts/agy_scratch.py`, repo-indépendant, MIT). Utilisé par deep-angle (staging scratch-then-move).
- `classify_source.py` : extraction du heredoc python dupliqué dans transcribe.md / video.md / media.md du repo. Entrée : source (+ question éventuelle) ; sortie : `KIND`, `ADD_DIR`, `WRITE_FILE`.
- `deep-agy.js` : le Workflow, adapté de `deep-research-agy.js` (schémas ANGLE/GLOBAL/REDTEAM/REPORT conservés, `agentType` → `agy-run`, helpers inline conservés car les scripts Workflow n'ont pas d'accès filesystem).
- `deep-agy-lib.mjs` + `render-report.mjs` : la lib de rendu (source de vérité) + son CLI, adaptés de `deep-research-lib.mjs` / `render-report.mjs`. Test de sync inline/lib repris, exécuté sous `bun`.

### Sorties : `docs/agy/<kind>/` relatif au projet courant

`transcripts/`, `video/`, `media/`, `converted/`, `research/` (+ `research/.deep/<date>-<slug>/` pour artefacts bruts). Séparé de `docs/research/` (search-deep). Slug : lowercase, non-alphanumérique → `-`, répétitions réduites, 60 chars max. Noms de fichiers par type : transcripts et video `<base>.md` ; media `<base>-<hash6 question>.md` ; converted et research `<date>-<slug>.md`.

### Langue : adaptative, défaut français

- Transcripts : toujours la langue de la source (jamais traduits).
- Gabarits structurés (breakdown vidéo, réponses media, frontmatters) : français par défaut, langue de la source si clairement autre. Remplace le défaut es-AR du repo.
- En-têtes vidéo : `## Résumé`, `## Scènes` (table `| Tramo | Qué se ve | … |` → `| Tranche (mm:ss–mm:ss) | Ce qu'on voit | Texte à l'écran / OCR | Audio (résumé) |`), `## Texte à l'écran`, `## Moments clés`.
- Interdits d'invention conservés tels quels (« ilegible » → « illisible », do NOT invent, [inaudible]).

## Contrat d'invocation agy (socle commun, non négociable)

Vérifié sur agy 1.1.3 local (ping headless OK le 2026-07-17) :

```
agy --dangerously-skip-permissions [--add-dir <dir>]... [--model '<label exact>'] \
    --print-timeout <N> --print "<prompt + OUTPUT INSTRUCTION write_file>" < /dev/null
```

- `--print` DERNIER flag avant le prompt (parseur Go).
- `< /dev/null` obligatoire (stdin hérité ouvert = hang non borné par `--print-timeout`).
- Réponse TOUJOURS écrite par agy dans WRITE_FILE (write_file), jamais lue depuis stdout (bug amont #76, apparemment corrigé en 1.1.3 mais le pattern fichier reste la ceinture de sécurité cross-version et donne un contenu propre sans extraction regex).
- `--add-dir` explicite pour chaque dossier lu ou écrit (source + CWD ; scratch seul pour deep-angle).
- Timeout Bash explicite = timeout agy + 60 s.
- Label modèle : chaîne EXACTE de `agy models` ; label inconnu = fallback silencieux vers le défaut.

## Flux

**Multimodal (ex. `/transcribe réunion.mp4 | décisions`)** : skill → `classify_source.py` (KIND=video, ADD_DIR, WRITE_FILE=`docs/agy/transcripts/reunion.md`) → `agy-run` (header MODE: transcribe) → un appel Bash agy (`--add-dir ADD_DIR --add-dir CWD`, 12 m) → `test -s WRITE_FILE` → lecture, retour verbatim → la skill présente résumé puis chemin.

**Deep (`/agy-deep <sujet> --depth L`)** : préflight agy (un Bash) → matrice de preuves + angles élaborés par Claude → plan gate affiché (sauf `--yes`) → `Workflow(scriptPath: scripts/agy/deep-agy.js, args {question, matrix, angles, depth, deepDir, date, title})` → rounds L≤2 / H≤4 : angles en parallèle via `agy-run` (schéma ANGLE), dédup `normURL+claim`, analyse de convergence Claude (schéma GLOBAL) → red-team agy sur claims centraux/mono-source (kill/downgrade/hold) → synthèse Claude (schéma REPORT) → rendu via lib → `docs/agy/research/<date>-<slug>.md` + ledger + artefacts `.deep/`.

## Gestion d'erreurs (hiérarchie du repo simplifiée pour macOS)

1. Préflight : agy absent ou non authentifié → message actionnable (installer ; lancer `agy` une fois en terminal pour l'OAuth) ; jamais de workflow lancé contre un agy mort.
2. WRITE_FILE absent après exit 0 : pas de retry aveugle → plan B transcript (`~/.gemini/antigravity-cli/brain/<cid>/.system_generated/logs/transcript.jsonl`, cid via `conversation=<cid>` dans le dernier `log/cli-*.log`, dernier `MODEL/PLANNER_RESPONSE.content`) → sinon échec verbeux avec extrait de log.
3. Signature `auth timed out` / `keyringAuth: timed out` dans le log : message ré-auth, retry INTERDIT (le modèle n'a jamais tourné, rien à récupérer).
4. Race Defender Windows (#217) : abandonnée, mono-plateforme macOS.
5. Workflow fail-open (repris du repo) : angle échoué → coverage dégradée annoncée (`failedAngleLabels`) ; red-team échoué → claim conservé (`hold`) ; synthèse nulle → rapport dégradé depuis les findings vérifiés.
6. Timeouts agy par mode : transcribe/media 6 m (audio) / 12 m (vidéo, URL) ; video 12 m ; doc-to-md 8 m (15 m si >20 pages) ; deep-angle 3 m (L) / 4 m (H) ; redteam 3 m.

## Modèles et coûts

- Défaut unique : `Gemini 3.5 Flash (High)` partout (cohérent avec search-deep), passé en flag `--model` per-invocation. Jamais via `settings.json` (levier global, race possible avec les autres agents agy de la session).
- Override ponctuel : les 5 skills acceptent `[--model <alias|label exact>]`, table d'alias minimale reprise de `config/model-map.json` (ex. `pro-high` → `Gemini 3.1 Pro (High)`).
- Facturation : tout le travail lourd sur Google AI Pro ; côté Anthropic ne restent que le forwarder haiku et l'orchestration deep (analyse de convergence + synthèse, sur le modèle de session).
- Free tier agy ≈ 10 RPM : le fan-out des angles reste ≤ 6 parallèles (dimensionnement du repo), pas de fan-out massif.

## Vérification de fin d'implémentation

Un échantillon réel par mode : un mp3 court, un mp4 court, une URL YouTube publique, un PDF scanné, une image ; plus un `/agy-deep --depth L --yes` sur un sujet bateau. Critères : fichier écrit au bon endroit, langue correcte (zéro fuite es-AR), timestamps présents pour vidéo/URL, plan B exercé une fois (simuler WRITE_FILE manquant), test de sync lib/inline vert sous `bun`.

## Décisions actées

| Décision | Choix | Raison |
|---|---|---|
| Forme | Import natif `~/.claude`, pas de fork GitHub | La valeur = prompts + patterns + 1 script ; ~/.claude déjà versionné ; chemin minimal (MIT) |
| Recherche | `/agy-deep` complète search-deep, ne le remplace pas | search-deep validé au quotidien ; zéro régression |
| Périmètre | Multimodal + deep uniquement | Choix explicite de Romain ; devils multi-provider et web ops écartés |
| Modèle wrapper | haiku | Plomberie pure |
| Sélection modèle agy | Flag `--model` per-invocation, labels exacts | settings.json = global, race ; flag OK sur 1.1.3 |
| Langue | Adaptative, défaut français | Remplace es-AR hardcodé |
| NotebookLM | Exclu intégralement | Tooling perso existant |

## Références

- Repo source : `~/dev/antigravity-plugin-cc-main` (MIT, `MarcosNahuel/antigravity-plugin-cc`, plugin v1.5.1).
- Fichiers clés : `plugins/antigravity/agents/agy-rescue.md` (modes + doctrine), `plugins/antigravity/scripts/{agy_scratch.py, deep-research-agy.js, deep-research-lib.mjs, render-report.mjs}`, `plugins/antigravity/commands/{transcribe,video,media,doc-to-md,deep-research}.md`, `plugins/antigravity/config/model-map.json`.
- Mémoire de session : `fork-antigravity-plugin` (leviers agy 1.1.3 vérifiés, quick wins appliqués le 2026-07-17, commit `0756aec`).
