# Multilingual Arena of Makers — Design (proposal only, not coded)

Makenna's vision, Nov 18, 2026: one day she wants to share Arena of Makers
across the world, so the game should not only show up in English. A player
should be able to play in their own native language — like Alexa skills,
which have one interaction model per language.

## Decisions (Makenna, Nov 18, 2026)

- **Argos Translate is the PRIMARY translation approach** — the free,
  on-the-player's-computer one that can translate live in the game — not
  just a fallback. AWS Translate stays as the optional better-quality
  source for shipped packs, but Argos is the main way, because it needs no
  keys, no account, and no private information.
- **No human checking is available.** Makenna, Josh, and all of their
  friends only know English, so there is nobody who could check a Spanish
  (or other language) translation. Translations are used as-is, best
  effort with the tools available.
- **Voices map per language.** When a language is added, each character's
  voice maps to that language: English voices speak in English, Spanish
  voices speak in Spanish, and so on for every language. Same giver, same
  personality, voice in the player's language.
- **NOT building now.** The focus is playing the game as it is. A language
  only gets added if people who speak that language come forward and ask
  for it — then it is built on demand using this plan.

## What "multilingual" means here

Three layers, all in the player's language:

1. **Installation** — the installer/setup screens show up in the player's
   language, not only English.
2. **In-game text** — menus, buttons, announcements, quest text, shop and
   More tab, everything the player reads or hears through NVDA.
3. **TTS voices** — Edge TTS speaks in the player's language too. If a
   player sets the game up in Spanish, the quest givers (Bolt, Marge, Pip,
   Dot, Gus, Belle) should speak Spanish, not English with a Spanish menu.

## How it would work (proposal)

- **One language pack per language.** Like Alexa's one-model-per-language:
  a file per language (for example `es.json` for Spanish) holding every
  string the game shows or speaks. English is the first pack; each new
  language is a new pack, not a rewrite of the game.
- **Language picked once, changeable anytime.** Picked at install or first
  launch, and changeable later in settings. The game remembers the choice.
- **Giver voices per language.** Each of the six quest givers needs a voice
  in each supported language — same giver, same personality, different
  language's Edge voice. Edge TTS already has voices in many languages
  (Spanish, French, German and more), but the exact voice for each giver in
  each language has to be picked and checked — a voice that exists in
  English does not automatically exist in Spanish.
- **Edge TTS facts, checked Nov 18, 2026 (web search):** the free edge-tts
  service has **400+ neural voices in 100+ languages**, no API key, no
  signup — the game already uses it. Each voice belongs to one locale
  (for example Spanish has Spain `es-ES` voices and Mexico `es-MX`
  voices, male and female in both). A voice can only read text written in
  its own language, so the game must switch the text AND the voice
  together — Spanish words through a Spanish voice. Edge also lists some
  voices as multilingual (one voice reading several languages), but the
  reliable approach is one voice per giver per language, picked from
  `edge-tts --list-voices` when that language is built.
- **Server text too.** Quest names and descriptions come from the server
  (the quests table / server functions), so translated quest text has to
  live server-side as well, not only in the game files.

## How translation would work (checked Nov 18, 2026)

Makenna and Josh only know English, so translation needs a service — same
as their Alexa games, which use AWS Translate.

- **Translate once, ship the result — never live in the game.** The English
  strings file is sent to the translation service once, when a language
  pack is built. The translated file (e.g. `es.json`) is saved in the repo
  and shipped with the game. The game itself never calls a translation
  service while someone plays: no keys in the game, no per-player cost,
  no internet needed for translation.
- **The game text is tiny.** Menus, buttons, announcements and quest text
  are maybe tens of thousands of characters per language. At these prices
  translating the whole game into one language costs well under a dollar.
- **Options, checked Nov 18, 2026 (third-party pricing trackers — verify on
  the official pricing page before budgeting):**
  - **AWS Translate — the natural fit.** $15 per million characters.
    Free tier was 2 million characters/month for the first 12 months, but
    sources disagree whether accounts created after July 15, 2025 still
    get it (newer accounts may get $200 in AWS credits instead). Makenna
    and Josh already use it for their Alexa games, so it is the same
    account and the same skill — no new setup, and the volume is so
    small the cost is pennies either way.
  - **Microsoft Translator (Azure) — best ongoing free tier.** Free F0
    tier 2 million characters/month, then $10 per million. 140+ languages.
  - **DeepL — best quality for European languages like Spanish**, but its
    free API plan (500,000 characters/month) is closed to new signups;
    new users get a one-time 1,000,000 characters that does not reset.
  - **Google Cloud Translation** — 500,000 characters/month free, then
    $20 per million.
- **Machine translation is a first draft.** A native speaker still needs to
  check the personality-heavy lines (giver dialogue, quest text) — a raw
  machine translation will sound flat or wrong in places.
- **Who runs it:** the translation step runs on a dev machine with the
  service account (Josh's computer with their AWS account, as with Alexa),
  not inside the game and not through Muse — Muse has no AWS connection.

## Continuous translation in the game (Makenna's question, Nov 18, 2026)

Makenna asked: can translation run continuously inside the game, so new
stuff gets translated as it is added — ideally with something built into
Python or Windows, so no private information (no keys) is involved?

- **Python has no built-in translator, and Windows has no translation API
  a Python desktop game can just call.** Checked Nov 18, 2026: Windows has
  built-in OCR and Live Captions, and Edge has translation, but there is no
  simple built-in Windows translation service for a wxPython game.
- **But there IS a Python library that does exactly what she asked for:
  Argos Translate.** Open source, MIT licence, a Python package
  (`pip install argostranslate`). It runs entirely on the player's own
  computer — no account, no API key, no cost, no internet after a one-time
  download of a language model (about 50 MB per language pair, e.g.
  English-to-Spanish). It is the same engine underneath LibreTranslate.
  Nothing leaves the player's computer.
- **How continuous translation would work with it:** the game ships the
  proper translated language pack (made with AWS Translate at build time)
  AND Argos as a live fallback. Any string that has no translation in the
  pack yet — because it is brand new — gets translated on the spot, inside
  the game, by Argos, and the result is saved (cached) so it is only
  translated once. Next game update, the proper AWS translation replaces
  the rough live one.
- **The catch is quality.** Argos is noticeably rougher than AWS Translate
  or DeepL — fine for menus and short lines, weaker for giver dialogue and
  personality. So: Argos guarantees nothing ever shows up untranslated,
  AWS Translate supplies the good translations that ship with each update.
  Best of both, and no keys anywhere in the game.
- **Practical notes:** the language model downloads once (needs internet
  that once, ~50 MB per language); translation itself runs on the player's
  CPU and is fast for short strings. Argos covers English to/from about 49
  languages; pairs that are not English go through English in the middle.
  Packaging needs checking when the exe is built — the models may be
  better downloaded on first run than bundled into the exe.

## What makes it hard (honest list)

- Every string in the game has to be pulled out of the code into the
  language packs first — right now the English words are written straight
  into the code. That is the big first step, and it touches a lot of files.
- Every new feature after that has to be translated into every language
  before it ships, or that feature shows up in English for some players.
- Some languages do not have six good Edge voices to match the six givers,
  and some voices sound very different across languages.
- Right-to-left languages (Arabic, Hebrew) and languages with very long
  words need layout care; that is a later step, not a first-language step.
- Translations need a real speaker of the language to check them — a
  machine translation alone will sound wrong in a game that is all about
  voices and personality.

## Sequencing (proposal)

- **Not now.** Current phases come first (Phase 24 creatures, then fighter
  switching, tag team, voice calls). Multilingual is a later, dedicated
  phase — Makenna said herself it will take a while to get to this point.
- **Start with one extra language as proof.** Spanish is the natural first
  one — it is Makenna's own example, and Edge TTS has strong Spanish
  voices. Get install + menus + giver voices working in Spanish first,
  then add more languages the same way.
- **English stays the fallback.** If a string is missing in a language,
  the game shows the English words rather than crashing or going silent.

## Open questions for Makenna (not answered)

1. Which language first after English — Spanish, or another?
2. Who translates? Makenna/Josh, friends who speak the language, or
   community players who want their language added?
3. Is the language picked at install, at first launch, or both?
4. Should quest giver voices keep the same personality in every language
   (same giver, closest-matching voice), or is any good voice in that
   language fine?
5. Should the game auto-detect the player's Windows language, or always
   ask?
