# Arena of Makers -> Magic Worlds (Alexa): conversion plan

Status: **PROPOSAL for Josh + Makenna. Nothing is built, deployed or pushed.** Written 2026-11-20 by Kiro.
Companion docs in the Magic Worlds repo: `BUBBLE_TYCOON_INTEGRATION_DESIGN.md` (the template),
`LOCALIZATION_PLAN.md`, `AUDIO_V2_DESIGN.md`, `TTS_COST_AND_EDGE_DEACTIVATION.md`, `CROSS_GAME_PVP_DESIGN.md`.
Companion docs in this repo: `MULTILINGUAL_DESIGN.md`, `PROPOSALS.md` (Phase tracker).

Tags: **[VERIFIED]** read from code, AWS or the repo today. **[PROPOSAL]** my recommendation.
**[OPEN]** needs a decision. **[NOT CHECKED]** I could not verify it.

---

## 0. Summary

1. **Arena becomes the fourth game in the Magic Worlds skill** (`game_mode = arena_of_makers`), the way Bubble Tycoon
   became the third. Same skill, same Lambda, same invocation name. Players say "switch to Arena of Makers".
2. **The data and the rules stay in Supabase.** The Alexa Lambda is a thin client that calls the same `arena_*` server
   functions the Windows game calls. No game rule is rewritten, so the two clients can never disagree. DynamoDB holds
   only the Alexa link, the audio-loop state and the cross-game rows. No migration to DynamoDB is needed.
3. **Accounts link by player code**, as the other games do, with one extra step so the public code is not the only
   key (section 4.3).
4. **Voices:** the narrator is Matthew (male) or Salli (female), the six quest givers get fixed Polly voices, and
   subscribers hear the generative engine while everyone else hears standard. The mapping lives in one table (section 5).
   On the PC the voice engine gets a setting, Edge (today's behavior, unchanged) or Polly (the same voices as Alexa).
5. **Sound and music can work on Alexa**, with caveats. Magic Worlds already mixes narration, effects and a music
   bed into one MP3 per step. Arena's effects can be laid over the speech with a small mixer change (section 6).
6. **Languages:** the skill has 17 locales and a working translation and localization pipeline. Arena plugs into it
   (section 7). Spanish first, as Makenna said.
7. **Order of work:** access and decisions, Supabase pieces, voice and audio foundation, skeleton on the development
   stage, combat and shop, idle loops, quests, PC Polly option, languages, cross-game, beta and certification (section 8).

---

## 1. What I looked at, and what I could not

### 1.1 AWS access on this machine [VERIFIED]

| Where | Profile | Account | Identity | What it reaches |
|---|---|---|---|---|
| WSL `~/.aws` | `Magic_realms` | 338593158389 | IAM user `magic-realms-dev` | The live skill's Lambdas, DynamoDB, S3 audio, Polly, Translate, API Gateway, CodeCommit repos `magic-realms` and `monster-paradise` |
| WSL `~/.aws` | `default` | 729059746559 | **root user** | CodeCommit repos `magic-worlds` and `bubble-tycoon` |
| Windows `~/.aws` | `magic-realms`, `default` | same two accounts | same | same |
| ASK CLI (WSL) | `default`, `Magic_realms` | n/a | n/a | **Token expired** (Amazon returned 400 on refresh) |

I used `Magic_realms` for all reads. I used `default` only to list CodeCommit, read commit history and download design docs.
I did not change anything in AWS.

### 1.2 What the Magic Worlds skill is made of [VERIFIED]

- Alexa Lambdas `MysticExistence-Alexa` and `MysticExistence-PC-API` (python3.12, 1,024 MB, **not in a VPC**, so they can
  call Supabase). Layers: `lameenc`, `miniaudio-mp3`, `edge-tts-py312`.
- DynamoDB: `MagicWorlds_CrossGame` (game mode, presence, Bubble Tycoon state), `MysticExistence`, `MonsterParadise*`,
  `MagicRealmsTranslations` (translation cache), and tables for other projects (`IdleRoots-*`).
- S3: audio buckets `monster-paradise-audio` (holds the shared `pcm/` mixer assets), `mystic-existence-audio-1773293500`.
  **Neither audio bucket has a lifecycle rule**, so generated clips are never deleted.
- Source: CodeCommit `magic-worlds` (account 729059746559), branch `main`. Last change today 07:54.
- Skill id `amzn1.ask.skill.4e248cb4-84e5-4326-9f82-b919770051c8`; 17 locales; invocation name `magic realms` (translated per locale).

### 1.3 What I could not check

- **[NOT CHECKED] The live and development interaction models.** The ASK CLI token is expired, so I cannot read them
  with SMAPI. I read the copy in the local clone instead, and that clone is **stale: 80+ commits behind CodeCommit**
  (it stops at Oct 29; the remote has Bubble Tycoon, the localization pipeline and a fixed game-switch slot).
  I did read the deployed Lambda code (downloaded from AWS, last modified Nov 19) and the newest docs straight from CodeCommit,
  so the findings in this plan are based on the current system, not the stale clone.
- **[NOT CHECKED] Alexa's limits** on intents and model size. Bubble Tycoon's design says the same: test on the development stage.
- Idle Roots and Knight Manager are separate projects. I did not read them.
- I did not open `dev_credentials.txt`, `auth_url.txt` or any key file.

### 1.4 Side findings (not Arena work, but you should know) [VERIFIED]

1. The WSL `default` profile holds **root access keys**. Root keys should not be used day to day. A least-privilege IAM user would be safer.
2. `Magic Realms/dev_credentials.txt` and `auth_url.txt` sit in plain text in the project folder.
3. The PC API appears to trust the `X-Player-Id` header alone as login (`_auth` in `pc_api.py`; I did not trace every route). If so, anyone who knows a player id can act as that player. Arena should not copy this.
4. `generative_voices.py` maps `'Takumi': 'Leo'` with the comment "Japanese generative Leo". Polly lists **Leo under pt-BR (Brazilian Portuguese)**, not Japanese. If that is right, a Japanese generative player hears Portuguese for that voice. Please verify.
5. Microsoft's Edge endpoint broke once already (token change, Oct 2026). The PC games still bundle Edge, so the same break can hit Arena on the PC. This is a reason to offer Polly as an option on the PC.
6. The local `magic-worlds` clone has uncommitted changes (`.ask/ask-states.json`, `.gitignore`). Do not overwrite it. I would work from a fresh clone.

---

## 2. How Magic Worlds works today [VERIFIED unless noted]

- **Router.** `lambda_function.py` looks up the player's `game_mode` (default `magic_realms`) in `MagicWorlds_CrossGame` and sends
  the request to that game's handler. `SwitchGameIntent` is handled globally. Audio events are routed by token prefix (`bt:`) or by game mode.
  Per-game maintenance scopes (`mp`, `mr`, `bt`), a kill switch (`BT_DISABLED`) and wrong-game hints exist.
- **Identity.** Player id = last 12 characters of the Alexa userId. Each game keeps its own 4-digit player code. Bubble Tycoon claims codes with a
  conditional put (`BTCODE#<code>`), so a code never has two owners, and resolves them with one `get_item`.
- **Subscription.** `realm_pass_active` / `dragons_blessing` on the Magic Realms and Monster Paradise profiles. Bubble Tycoon only reads them.
- **Voices.** Polly only; Edge is off on Alexa (`TTS_EDGE_ENABLED=false`). `TTS_GENERATIVE_ENABLED=true` and a 2-entry allowlist: **subscribers get
  generative, everyone else standard** (`generative_voices.py`, `db._generate_polly_pcm`). `TTS_STITCH_ENABLED=true`: fixed text fragments are synthesized once and cached; only numbers are synthesized live.
- **Why Edge was dropped on Alexa** (`TTS_COST_AND_EDGE_DEACTIVATION.md`, `EDGE_EVERYWHERE_PLAN.md`): Edge adds about 0.8-1.1 s cross-internet against about 0.2 s for Polly in-region.
  Interactive turns have an 8 s hard limit and no latency-hiding window, so Edge fell back to Polly and the voice kept switching. It is also an unofficial endpoint.
- **Audio v2** (`AUDIO_V2_DESIGN.md`, `audio_mix.py`, `audio_v2.py`): one pre-mixed MP3 per step, rendered one clip ahead.
  Render on `PlaybackStarted`, enqueue on `PlaybackNearlyFinished`. Alexa forbids a Play directive in response to `PlaybackStarted`.
  Pure-Python PCM mixer (16 kHz mono signed 16-bit), `lameenc` MP3 at 48 kbps, narration gain 5x, music bed ducked to 45% under speech.
  Measured for Bubble Tycoon: a full 240 s narrated clip takes about 4.6-5 s on Lambda, about 190 MB of memory; the Alexa function timeout is 120 s.
- **Translation.** `translate.py`: AWS Translate for 9 languages (es, de, fr, it, pt, ja, hi, ar, nl), cached in `MagicRealmsTranslations`, with a number-fidelity check
  (a translation that changes a number is discarded). Locale-matched Polly voices.
- **Models and localization.** 17 locales, about 144 intents, 34 slot types, per-locale invocation names. `LOCALIZATION_PLAN.md`: add localized phrases next to the English ones,
  quality-gate each with Comprehend and a Translate round trip, clash guard, NLU regression with `profile-nlu`. **Standing rule: a feature is not done until its commands are localized in all locales.**
- **Release gating.** The skill is in certification review. Bubble Tycoon commands exist only in the **development** model, so only beta testers reach it. The manifest is locked during review; development-stage model deploys are allowed.
  Deploy order lesson: en-US first, wait for `SUCCEEDED`, then the other locales.

### How Bubble Tycoon was added (the template)

Phase 0 NLU acceptance harness; 1a foundation (package, state, router, switch); 1b audio spine (beds, tokens, loop); 1c identity (tutorial, name, gender, own player code, recovery);
2 core loop; 3 pets and shops; 4 combat, library, dungeon, palace; 5 forest; 6 social; 7 perks; 8 two-account test, then certification.
Lessons it recorded: a wrong SFX encoding crashed purchases (use 24 kHz mono 48 kbps MP3, no metadata); the game-name slot must be a custom type, not free text;
reuse existing intents but expect catch-all intents to steal phrases; store big state as one JSON string; optimistic version checks for concurrent writes.

---

## 3. What Arena already has that helps [VERIFIED]

- Every game rule runs in SQL functions called by a **session token**. Timers (upgrades, repairs, quests) use server time. That fits Alexa well: the Lambda only asks and speaks.
- `arena_*` calls return finished spoken lines in the first person (Phase 28), plus structured data (credits, levels, quest, giver, reputation).
- Fight and quest text is templated, so the stitcher caches most of it.
- The Alexa Lambda is in Lambda region us-east-1; the Supabase project is in us-west-2. Expect about 60-80 ms extra per call [NOT CHECKED, typical cross-region latency]. A fight is one call.
- `player_code` is already the **primary key** of the `players` table, so a lookup by code is instant and unique.
- 20 client calls plus 6 account calls are already contract-tested against the migrations (`test_migrations.py`).

---

## 4. Architecture

### 4.1 Arena as a fourth game [PROPOSAL]

- New package `lambda/arena_of_makers/` beside `bubble_tycoon/`: `handler`, `state`, `identity`, `link`, `voices`, `speech`, `audio`, `loop`, `tutorial`, `supabase_client`.
- Router changes: `game_mode = arena_of_makers`; `GameNameType` gets a value `arena of makers` (synonym `makers`; **not** bare "arena", because Monster Paradise has a Meadow Arena);
  maintenance scope `aom`; kill switch `AOM_DISABLED`; wrong-game hints; audio token prefix `aom:`; `check_wrong_game_hint` sets.
- Alexa-side state: one DynamoDB item per player in `MagicWorlds_CrossGame` (`SK=AOM_STATE`): link, tutorial step, loop tokens and next-clip URL, locale, voice choices, cached subscription flag. Small.
  **Game state is not stored here.** It stays in Supabase.

### 4.2 Why not move Arena to DynamoDB [PROPOSAL]

All rules would have to be rewritten from SQL into Lambda code, and the Windows game would have to be re-pointed. Two copies of the rules would drift. Supabase can serve both clients.
DynamoDB tables stay reachable from the Lambda for cross-game features (section 4.6).

### 4.3 Linking by player code [PROPOSAL]

Your decision to use the player code instead of OAuth fits Arena: the code is already unique and indexed.
One problem to design around: **in Arena the player code is public** (friends look each other up by it) and there are only 10,000 codes.
Magic Realms recovery today is "say the code, then yes", which would let anyone take over an Arena account. So the code identifies; something private approves.

- **Flow A (recommended): PC issues a one-time code.** In the game: More > Link Alexa. The server makes a 6-digit code (10 minutes, single use, stored hashed).
  The player says it to Alexa. This is the same pattern as the existing `/v1/link` + claim in the PC API.
- **Flow B (uses the 4-digit code): Alexa asks, the PC approves.** The player says their code to Alexa; the next time the signed-in PC game polls, it shows "Approve Alexa?".
  Costs a poll or a push in the PC game.
- **Flow C: Alexa-first players.** Alexa onboarding (name, gender, robot or chef, random 4-digit code, like Monster Paradise) creates an account with **no password**.
  Later, "Claim my Alexa account" on the PC sets a username and password. Needs a migration (`password_hash` is `not null` today) and a rule for username collisions.
- A new Alexa device just links again. Because progress is stored under the player code, **nothing has to be moved** (Bubble Tycoon had to re-key its state).

### 4.4 How the Lambda acts for a player [PROPOSAL]

- New service-only function `arena_skill_token(alexa_id)` mints a short-lived session token for the linked player. The Lambda then calls the **existing** `arena_*` functions unchanged. No rule is duplicated, and old Windows games keep working.
- Other new functions: `arena_make_link_code`, `arena_skill_link_claim`, `arena_skill_resolve_token` (used by the PC Polly endpoint), an Alexa heartbeat.
- **Security.** These functions are granted **only to `service_role`**, not to `anon` or `authenticated`. This is a deliberate exception to the "Rules that keep the game safe" in `supabase/README.md`, which say every new `public.arena_*` function is granted to `anon, authenticated`; the README must say why.
  The `service_role` key is stored in AWS Secrets Manager or an encrypted Lambda environment variable and **never** in the repo or the game.
  `service_role` bypasses all row security, so a hardening step later is a dedicated database role that can run only these functions.
- Every change is a new migration, tested with `test_migrations.py` and the Supabase Preview check, per the README.

### 4.5 Time-based mechanics on Alexa [PROPOSAL]

Upgrades and repairs already run on server time and finish whether or not anyone is playing. The **quest clock** is different: on the PC it runs only while the player is in the hangout with quests started.
On Alexa, the idle loop is the hangout. Stop, Pause, session end and playback failure must call `arena_pause_quest`. A silent drop (no event arrives) needs a rule: if the Alexa heartbeat is older than N minutes, the server treats the quest as paused. **[OPEN]** pick N.

### 4.6 Cross-game features [PROPOSAL; depends on the link]

- **Possible now with the link:** presence ("who is online", already in `MagicWorlds_CrossGame`), the shared subscription flag (read-only, as Bubble Tycoon does), Crew invites by player code.
- **Cross-game PvP** (`CROSS_GAME_PVP_DESIGN.md`): Arena's five stats (strength, defense, health, speed, luck) map almost one to one onto the design's normalized stats (attack, defense, speed, luck, hp).
  Arena numbers are small next to Monster Paradise's millions, so the log-scale normalization in that doc applies. A rating row `PVP_PROFILE` is written by the Lambda; the Windows game never touches DynamoDB.
  Arena has no player-versus-player fights yet (Phase 14 in the tracker), so this waits for that.
- The Windows game **cannot** read DynamoDB (no AWS keys on the PC, and there should be none). Cross-game data reaches the PC only through a Lambda endpoint that first checks the player's Arena session token.

---

## 5. Voices

### 5.1 Today and the mapping [VERIFIED facts; the table is a PROPOSAL]

Today the PC uses Edge: player voice `en-US-GuyNeural` / `en-US-AriaNeural`; givers Bolt = Christopher, Marge = Jenny, Pip = Eric, Dot = Michelle, Gus = Andrew, Belle = Emma.
Polly voices that exist in **both** standard and generative: Matthew, Joanna, Salli (US); Brian, Amy (GB); Russell (AU). No generative version: Joey, Justin, Kendra, Kimberly, Ivy, Emma. No standard version (subscribers only): Stephen, Kenneth, Nate, Danielle, Ruth, Tiffany.

The shared substitute map in `generative_voices.py` sends Justin and Joey to Matthew and Kimberly to Salli. That would make a giver sound like the narrator, the same conflict Bubble Tycoon hit with its wizard.
So Arena picks **one voice per tier locally**, as Bubble Tycoon does:

| Role | Standard (everyone) | Generative (subscribers) | Reason |
|---|---|---|---|
| Narrator, male player | Matthew | Matthew | Magic Worlds default, exists in both |
| Narrator, female player | Salli | Salli | same |
| Bolt (male, gruff) | Joey | Stephen | distinct from narrator in both tiers |
| Pip (male, excitable) | Justin | Nate | same |
| Gus (male, old grill master) | Brian | Brian | exists in both |
| Marge (female, warm) | Joanna | Joanna | exists in both |
| Dot (female, calm) | Kendra | Danielle | |
| Belle (female, cheerful) | Kimberly | Tiffany | |

**[OPEN] This is a starting point and has to be auditioned.** I cannot hear voices. I can generate audition clips for every giver in both tiers (a few cents of Polly) so you and Makenna can choose.
Brian is also Bubble Tycoon's merchant; shared voices across games are fine if you want them.

### 5.2 Other languages [VERIFIED counts]

Polly has few voices per language, so six distinct givers per language is not possible (counts below are the main language code only):
es-ES 3 M + 3 F; es-US 3 M + 2 F; es-MX 1 M + 1 F; de-DE 3 + 3; fr-FR 3 + 3; fr-CA 1 + 2; it-IT 3 + 3; pt-BR 3 + 3; ja-JP 1 M + 3 F (no generative in this listing); nl-NL 1 + 2; arb 0 M + 1 F; hi-IN none under its own code.
**[PROPOSAL]** A giver is a gender plus a personality. In each language, assign the available voices of that gender to the givers in rotation, and reuse a voice when there are not enough.
Makenna's MULTILINGUAL_DESIGN says "same giver, voice in the player's language"; Polly's supply decides how distinct they can be.

### 5.3 PC: a voice-engine setting [PROPOSAL]

- **Setting:** Voice engine = Edge (default, **behavior unchanged**) or Polly.
- **Polly path:** the PC sends the line, the role (narrator or giver name) and its session token to a new Lambda endpoint. The Lambda checks the token with `arena_skill_resolve_token`, looks up the engine tier
  (linked subscriber = generative, otherwise standard), allows **only voices from the mapping table**, synthesizes, and returns the MP3. The PC caches it by hash and plays it through the existing `pygame.mixer.music` path.
- **Do not reuse** `MonsterParadise-PollyProxy`: it has no authentication and a fixed voice table.
- **Fallback:** if Polly fails, fall back to Edge, then to text only, using the Phase 27 rules (a failed line never stalls later lines).
- **Cost control:** per-player daily character quota, a maximum text length, and the stitcher's fragment cache. Unlinked PC players get standard voices.
- The server already sends each giver's name, so the PC maps by giver name. No server change is needed, and the Edge names in `quests.py` stay for older games.

---

## 6. Sound and music

### 6.1 How the PC mixes now [VERIFIED, `sounds.py`]

Voice narration plays on `pygame.mixer.music`. Effects are `Sound` objects on their own channels. The music loops on Channel 2, quest ambience on Channel 3.
Volumes: effects 0.4 by default (a setting), music 0.5 of that, quest ambience 0.25 of that. Effects play **at the same time** as the speech: `_play_sound_for_line` starts the sound as the matching line is spoken.
A spoken line never cuts the music, and music never cuts a line.

### 6.2 How Magic Worlds mixes [VERIFIED]

Alexa plays one stream. Everything is mixed on the server into one MP3 per step. `mix_multi_step` builds: music bed looped under the whole clip, ducked to 45% while anyone speaks;
voice segments in order with a gap; an optional effect **before** each line (`segment_sfx`). Effects are placed **in sequence, ahead of the line**, not on top of it.
Short interactive replies use SSML `<audio>` for effects. After a spoken reply interrupts the stream, a cached music-only clip restarts the bed.

### 6.3 Can Arena work this way? Yes, with these changes [PROPOSAL]

| Arena element | Files [VERIFIED] | On Alexa |
|---|---|---|
| Fight music | `music_fight.mp3`, 93 s | Looped as the bed of the fight loop clip |
| Hangout music | `music_hangout.mp3`, **323 s** | Longer than the existing 300 s step cap. Trim to under 300 s or split into two beds with a continuation offset **[OPEN]** |
| Quest ambience | `ambience_gathering.mp3` 170 s, `ambience_cleaning.mp3` 60 s | Bed under the quest voices, instead of the music, as on the PC |
| Player and creature sounds | 8 `.wav` files (0.4-5.6 s) and 18 `npc_*.ogg` files (0.2-5 s, two 5 s files trimmed to 2 s on the PC) | Per-line effects |

- **Layering.** Add an **overlay mode** to the mixer: an effect is added into the foreground at the start of its line (sample-wise add, clamped), as on the PC, instead of being placed before it.
  Keep sequence mode for the other games. The effect volume stays below the voice, as on the PC.
- **Assets.** Convert every file once, offline, to 16 kHz mono PCM, level it (Bubble Tycoon used RMS about 3,000 per place), and upload to `pcm/audio/aom_*` and `pcm/sfx/aom_*`.
  For SSML `<audio>` use **24 kHz mono 48 kbps MP3 with no metadata**. PCM sizes: hangout 10.3 MB, fight 3.0 MB, gathering 5.4 MB, cleaning 1.9 MB.
- **Interactive replies** (a manual "fight"): one call plus Polly, with the 8 s limit. Fight lines are templated and cache well. Build the reply as speech with `<audio>` effects, or as a single pre-mixed clip if it renders fast enough.
  **Measure on Lambda before choosing.** Fall back to plain speech if a render is late.
- **Idle loops** (auto-fight, hangout): the Audio v2 chain, one clip ahead. Pure-Python mixing cost grows with clip length; Bubble Tycoon does 240 s in about 5 s. Measure Arena's own clips.
- **Limits.** One stream, no per-category volume control for the listener; the ratios are fixed in the mix. A spoken reply stops the stream, so the music must be restarted.
- **Licences.** Two music tracks are CC-BY (credit lines in `SOUNDS.md`). The skill description or in-skill credits must carry the attribution. The rest are CC0 or Pixabay.

---

## 7. Languages

### 7.1 What exists [VERIFIED]

- 17 locales: ar-SA, de-DE, en-AU, en-CA, en-GB, en-IN, en-US, es-ES, es-MX, es-US, fr-CA, fr-FR, hi-IN, it-IT, ja-JP, nl-NL, pt-BR.
- Spoken output is translated at runtime by the shared `translate.py` and spoken by locale voices. Recognition (what the player says) comes from the per-locale models.
- Localization of the models was automated. As of the plan's last update (Nov 8): Phase 1 complete for 12 locales, Phase 2 core complete, Phase 3 (the single deploy and formal NLU evaluation) not done. Nothing is live-deployed; certification is pending. **[NOT CHECKED]** whether this has moved since.

### 7.2 What Arena needs [PROPOSAL]

1. **Output.** Arena's text is English from SQL functions. Translate the **finished lines** in the Lambda with `translate.auto_translate`, as the other three games do. No server change.
   Fight and quest lines repeat a lot, so the cache hit rate is high, and the number check protects damage and credit amounts. A later option is stable message IDs from the server, which would translate each template once.
2. **Glossary.** Creature names, giver names, "Second Wind", "credits" and "quest level" need fixed translations so the translator does not rename them. Names stay in English.
3. **Voices.** Locale voices per section 5.2. Wrap numbers for non-English voices as `_wrap_numbers_for_voice` does.
4. **Recognition.** Arena's new intents, slot values and synonyms in all 17 locales, through the existing pipeline (extract, translate, gate, merge, deploy to development, `profile-nlu` regression). Spanish first (es-ES, then es-US, es-MX).
5. **Quality.** Nobody on the team reads these languages. Use the existing gate (language detection plus a round-trip translation) and keep English as the fallback. A native-speaker review is still needed before launch.
6. **PC.** Makenna decided Argos Translate is the PC's primary translation. The Alexa side uses AWS Translate. They do not conflict, but sharing one **glossary** and, later, one strings catalog keeps both in step.

---

## 8. Phases

Each phase ends when its "done when" line is true. Nothing goes live until certification. Sizes: S about a day, M a few days, L a week or more [PROPOSAL, my estimate; none of this has been measured].

### Phase 0: Access and ground truth (S)
- Re-authorize the ASK CLI (the token expired; Makenna rebuilt it once through the LWA login URL). Then pull the development and live models for all 17 locales and diff them against the repo.
- Fresh clone of CodeCommit `magic-worlds` (install `git-remote-codecommit`, or use the API); keep the stale clone untouched.
- Decide the access I use: a least-privilege IAM user for Kiro, instead of root keys.
- Confirm the voice flags and allowlist, and Alexa's intent and model limits (empirically, on development).
- **Done when:** both models are pulled and diffed, a fresh clone builds, and I can deploy a model to the development stage for en-US.

### Phase 1: Decisions (S, Josh + Makenna)
- Answer section 9. Update `PROPOSALS.md`.
- **Done when:** the open decisions are answered or consciously deferred.

### Phase 2: Supabase pieces (M)
- Migrations: link table and codes, `arena_skill_token`, `arena_skill_link_claim`, `arena_skill_resolve_token`, heartbeat, Alexa-first account (nullable password), service-only grants.
- Extend `test_migrations.py` and add contract tests for the Lambda client. Update `supabase/README.md` for the new grant pattern.
- **Done when:** replay passes, the Supabase Preview check passes, old Windows games work unchanged, and a test link and token round trip works.

### Phase 3: Voice and audio foundation (M, offline)
- Voice table module shared by the Lambda and the PC, plus audition clips; Josh and Makenna pick voices.
- Convert, level and upload every sound and bed; trim or split the hangout track; prepare 24 kHz MP3 effects for SSML.
- Mixer overlay mode with tests; render-time measurements on Lambda for a fight clip and a long bed; a list of fixed Arena lines to pre-warm in the stitcher cache.
- **Done when:** the audition is approved, the assets are in S3 with matching checksums, and a hand-built test clip with overlaid effects plays on a real Echo.

### Phase 4: Skeleton in Magic Worlds, development stage (M)
- Package, router changes, `GameNameType`, onboarding (new or returning, name, gender, robot or chef, code), link flow, "status", and a speech-only "fight".
- en-US development model only, with a `profile-nlu` acceptance harness and a regression baseline for the existing games.
- **Done when:** Josh and Makenna can say "switch to Arena of Makers", link an account, hear their status, and the other three games still resolve every baseline phrase.

### Phase 5: Combat, shop and stats with sound (L)
- Manual fight with creature sounds, upgrades, max affordable with a confirm, stat spending, respec, repair status, first-person lines, number speech.
- Measure interactive timing against the 8 s limit; choose SSML or pre-mixed.
- **Done when:** a full fight, an upgrade and a stat spend work by voice, with the right sounds, inside the time limit.

### Phase 6: Idle loops (L)
- Auto-fight loop on the Audio v2 chain, fight music bed, repair and upgrade announcements, loop resilience (render on started, enqueue on nearly finished), music restart after a spoken reply.
- **Done when:** a multi-hour session runs with no silent stop (watch the chain diagnostics).

### Phase 7: Hangout quests (L)
- Quest loop with giver voices, ambience beds, the five-minute progress line, reputation tiers, gifts, quest stats, and the pause and heartbeat rules from section 4.5.
- **Done when:** a quest finishes by voice, a paused quest resumes with its remaining time, and a dropped session does not run the clock.

### Phase 8: PC Polly option (M, can run beside Phases 4-7)
- Lambda endpoint, voice-engine setting, client caching, quota, fallback chain, tests. Edge stays the default and its behavior does not change.
- **Done when:** with the setting on Polly, the narrator and all six givers speak with the Alexa voices, a Polly outage falls back to Edge, and with the setting on Edge nothing differs from today.

### Phase 9: Languages (L, repeated per language)
- Runtime translation and glossary, locale voices, model localization in the agreed order with the quality gate and regression checks, development stage first.
- **Done when,** per language: Arena's commands resolve in that locale, Arena's narration is spoken in that language with the right voice, and the number check shows no changed amounts.

### Phase 10: Cross-game (M, after launch)
- Presence, Crew, then PvP rating once Arena has player fights.
- **Done when:** a linked player appears in the cross-game table and the chosen feature works without writing to Arena's data outside Supabase.

### Phase 11: Beta, cost, certification, launch (M)
- Two-account end-to-end test. Watch Polly characters per day. Add an S3 lifecycle rule for generated clips. Update the skill description (four games), testing instructions and privacy policy, and add the music credits.
- Submit with the next certification. Keep `AOM_DISABLED` as the kill switch.
- **Done when:** certification passes and the live model includes Arena.

---

## 9. Decisions needed

1. **Name and switch phrases:** "arena of makers" and "makers" (not bare "arena")?
2. **Linking:** Flow A, B, or both? Do you want Alexa-first accounts (Flow C)?
3. **Secret handling:** service key in Secrets Manager now, with a restricted role later?
4. **Voices:** approve or change the table in 5.1 after the audition. Is the narrator Matthew and Salli?
5. **PC Polly:** unlinked players get standard; is a daily character quota acceptable? Does Edge stay the default?
6. **Languages:** Spanish first? Which languages at launch? Runtime translation of finished lines, or message IDs later?
7. **Quest clock on Alexa:** the heartbeat timeout N, and whether Stop should always pause.
8. **Hangout music:** trim to under 300 s, or split?
9. **Subscription perks for Arena:** this waits for Josh (standing rule).
10. **Access:** a least-privilege IAM user for me, and a fresh ASK login.
11. **Certification timing:** ride the next submission, and keep Arena development-stage only until then?

---

## 10. Risks

- **Two databases.** Cross-game writes cannot share a transaction. Keep one owner per kind of data and make cross-game writes safe to repeat.
- **Latency.** Cross-region Supabase calls, Polly generative synthesis and the 8 s limit. Mitigation: stitching, parallel synthesis, a late-render fallback to plain speech.
- **Certification.** The manifest is locked during review, and Arena's commands reach players only after the next approval.
- **Model size.** The model already has about 144 intents. Arena adds roughly 25 (my estimate) across 17 locales. Limits are not documented; test on development.
- **Shared model.** A new phrase can steal a command from another game. The clash guard and the NLU regression run before every deploy.
- **Stale local clone.** Work from a fresh clone, never the old one.
- **Edge on the PC.** It already broke once. That is the reason for the Polly option.
- **No native reviewers.** Machine translation gates catch wrong language and wrong meaning, not tone.
