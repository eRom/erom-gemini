# erom-gemini — les yeux et les oreilles de Claude Code

Plugin Claude Code. Claude Code ne voit ni n'entend les médias : il ne peut ni
écouter une note vocale, ni regarder un screencast, ni océriser un PDF scanné.
Gemini est nativement multimodal. Ce plugin offloade ces quatre capacités vers
l'Antigravity CLI (`agy`) et récupère un markdown propre dans le projet courant.

| Skill | Entrée | Sortie |
|---|---|---|
| `transcribe` | audio, vidéo, URL YouTube/distante | transcript intégral dans la langue d'origine + résumé (timestamps pour vidéo/URL) |
| `video` | vidéo, URL | breakdown **visuel** : scènes horodatées, OCR du texte à l'écran, moments clés |
| `media` | audio, vidéo, image, URL | réponse à une question ciblée, avec repères temporels |
| `doc-to-md` | PDF, docx, image, HTML | markdown fidèle : titres, tables, listes, blocs de code préservés |

Choisir entre les trois skills média : **transcribe** quand tu veux tout ce qui
est *dit*, **video** quand tu veux tout ce qui est *montré*, **media** quand tu
as une question précise et pas besoin du reste.

## Usage

```
/erom-gemini:transcribe <fichier|url> [focus] [--model <alias>]
/erom-gemini:video      <fichier|url> [focus] [--model <alias>]
/erom-gemini:media      <fichier|url> | <question>  [--model <alias>]
/erom-gemini:doc-to-md  <fichier> [focus] [--model <alias>]
```

Exemples :

```
/erom-gemini:transcribe ~/Downloads/note.ogg décisions et actions
/erom-gemini:video https://youtu.be/xyz les slides d'architecture
/erom-gemini:media reunion.mp4 | qu'est-ce qui est décidé vers 2:30 ?
/erom-gemini:doc-to-md ~/Documents/contrat.pdf 45 pages
```

`--model` est optionnel ; sans lui, `Gemini 3.6 Flash (High)`.

| Alias | Modèle |
|---|---|
| `gemini-3.6-flash-high` | Gemini 3.6 Flash (High) — défaut |
| `gemini-3.1-pro-high` | Gemini 3.1 Pro (High) |

Une valeur absente de la table est passée telle quelle à `agy`, supposée être un
label exact (`agy models` donne la liste).

## Sorties

Tout atterrit sous `docs/gemini/` du projet courant :

```
docs/gemini/transcripts/<slug>.md
docs/gemini/video/<slug>.md
docs/gemini/media/<slug>-<hash-question>.md
docs/gemini/converted/<date>-<slug>.md
```

## Pré-requis

| Binaire | Auth |
|---|---|
| `agy` ([antigravity.google](https://antigravity.google)) | lancer `agy` une fois dans un vrai terminal (OAuth) |

`$AGY_BIN` prime si défini, sinon `agy` sur le PATH, sinon `~/.local/bin/agy`.
Le forwarder fait son préflight et s'arrête proprement si le binaire manque ou
si l'auth headless a expiré — jamais de transcript inventé sur un moteur mort.

## Limites connues

- Audio/vidéo > ~30 min et vidéos > ~15 min peuvent dépasser le timeout
  (6 min audio, 12 min vidéo) : découper avec `ffmpeg` en amont.
- Bug amont `agy` #76 : la sortie stdout peut se perdre. Le forwarder le
  détecte (fichier vide) et récupère la réponse depuis le transcript de la
  conversation ; il distingue ce cas d'une auth expirée, qui elle n'est jamais
  retentée.
- `video`, colonne « Ce qu'on voit » : Gemini peut inventer du mouvement sur un
  plan fixe — observé une fois, un curseur d'édition décrit comme clignotant et
  se déplaçant sur une vidéo faite d'une seule image bouclée. Le prompt interdit
  explicitement l'invention de mouvement depuis la 0.1.2, sans garantie absolue.
  **L'OCR (`## Texte à l'écran`) est fiable** ; c'est la description des
  événements visuels qui demande un œil critique sur un screencast, où un
  faux mouvement de curseur est plausible et indétectable sans revoir la vidéo.

## Composants

```
agents/
  gemini-run.md              forwarder agy : 4 modes (transcribe, video, media, doc-to-md)
scripts/agy/
  classify_source.py         source → kind / add_dir / write_file
  recover_transcript.py      plan B : récupère la réponse depuis le transcript agy
  tests/                     python3 tests/test_classify_source.py && python3 tests/test_recover_transcript.py
skills/
  transcribe/ video/ media/ doc-to-md/
```

Le plugin est autonome : aucun script ni agent hors de sa racine, stdlib Python
uniquement. Les skills résolvent la racine (`${CLAUDE_PLUGIN_ROOT}`, ou deux
niveaux au-dessus du base directory de la skill) et la passent au forwarder via
le header `PLUGIN_ROOT` — le forwarder ne devine jamais son propre chemin.

## Licence

MIT — Romain Ecarnot.
