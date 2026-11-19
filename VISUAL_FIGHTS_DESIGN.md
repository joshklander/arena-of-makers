# Visual fight scenes — design (Makenna's vision, Nov 18, 2026)

Status: vision only, NOT building now. Makenna has not decided when —
" I don't know if I'm going to do it right away or wait for a while."

## The vision (her words)

Moving images in fights: your character on one side, the enemy on the
other, little images that show the fight in real time, like mobile games —
with visual indicators for who's winning, who's losing, who's dying.

## How it would work

- **Layout**: the Combat tab gains a picture area. Your fighter on the
  left, the enemy on the right, a health bar above each one.
- **Moving pictures, sprite-frame style**: a few still pictures per
  fighter — standing, attacking, hurt, dodging, winning, defeated —
  swapped in sequence as the fight plays. Small movements on top:
  the attacker slides forward on a hit, the one hit flashes, the
  loser falls or greys out. This is how most 2D games do it, and it
  fits this game better than video clips (wxPython does have a video
  player on Windows, but it is heavier and less reliable).
- **Indicators**: health bars shrink and shift colour (green to yellow
  to red) as health drops; the fighter who is ahead gets a glow or a
  marker; the defeated one changes pose. The game already knows all
  of this — every round already produces the events (hit, crit, dodge,
  heal, win, lose) that drive the spoken narration. The pictures would
  just listen to those same events.
- **Moving video route (Makenna asked Nov 18, 2026)**: yes, real video
  is possible too. wxPython has a built-in video player
  (`wx.media.MediaCtrl`) on Windows that can play short MP4 clips
  inside the game window, and Maren can generate short clips with her
  video tool (one per fighter action, or per special moment). The
  clips would live on the player's computer like sounds and pictures.
  Trade-offs vs still pictures: (1) video files are heavy — 10
  creatures times several actions is a lot to download and update;
  (2) each generated clip is drawn fresh, so the same robot can look
  different from clip to clip, while one still picture per pose stays
  consistent; (3) a clip has a fixed length, but the spoken narration
  timing varies, so a clip can run long and overlap the next round —
  stills can be held exactly as long as needed; (4) video playback
  depends on the Windows media system and can stutter or fail on some
  machines, while swapping pictures never fails; (5) generating video
  uses more Muse usage than stills. Recommendation: hybrid — still
  pictures with code movement (slide, shake, flash) for the fight
  itself, and short video clips only for special moments (victory
  celebration, a new creature appearing). Open question: try one clip
  first (e.g. a victory clip) before committing to video anywhere.
- **Where pictures come from**: generated from a text description
  (Maren's image tool), one set per creature/fighter, uploaded to
  GitHub through the website like the sounds (binary files — the
  GitHub tools cannot push them), kept in an `images/` folder, and
  loaded from the player's own computer while playing — no internet
  needed mid-fight, same as sounds.
- **What the game has today**: no pictures at all. The Combat tab is
  a text log plus lists; pygame is used only for sound, never its own
  window (main.py: "Only the sound mixer is used, never pygame's own
  window"). So this adds a brand-new visual layer, not a tweak.

## Server's role in syncing video and narration (Makenna asked Nov 18, 2026)

Yes, the server can help — but it cannot do the syncing alone, and here
is why, honestly:

- The server is already the referee: it decides what happens each
  round and in what order, and sends that result to the player's
  computer. It could send a per-round "director's script" along with
  the result — which clip to play, which line to speak — so the
  computer knows the plan for the whole fight up front.
- But the exact moment-to-moment sync has to happen on the player's
  computer, because only the computer knows when the voice actually
  finishes speaking (Edge TTS speed, the player's machine, network
  to the voice service) and when the clip actually ends. A clip has a
  fixed length; speech does not. So the computer starts the clip and
  the spoken line together, and waits for whichever finishes last
  before the next round — the same way it already waits for narration
  to finish before the next auto-fight round today.
- The server must NOT stream the videos: they are big (one short
  victory clip generated Nov 18, 2026 was 12.5 MB) and Supabase is
  not a video service — streaming would lag and cost. Clips live on
  the player's computer, like sounds.
- Where the server genuinely helps: in player-vs-player fights it
  sends the same round script to both players, so both screens show
  the same fight in step (within network delay).
- Easiest clip to sync: the victory clip — it plays once at the end
  with a short line ("You win!"), so there is nothing for it to
  overlap. Round-by-round clips are the hard case.

## Accessibility — the important part

The pictures are extra, for sighted players. They never replace the
spoken fight. Narration, sounds and music stay exactly as they are,
and a blind player loses nothing — the fight still plays fully
through sound. The visuals show what the narration already says.

## Toggles — personalization (Makenna, Nov 18, 2026)

Two separate toggles, both personal preference, both in Settings:

1. **Visuals on/off.** Sighted and low-vision players who want the
   pictures and videos turn them on; blind players who do not need
   them turn them off. Default: off, so nothing changes for players
   who play by sound today — visuals are opt-in.
2. **Narration on/off.** Turning it off silences ALL of the Edge
   TTS talking — round-by-round fight narration, the five-minute
   quest progress updates, upgrade and quest announcements — while
   the sound effects, music, and quest ambience loops all keep
   playing as normal. Two use cases (Makenna, Nov 18, 2026): a
   sighted player who just wants the visuals with no talking, and a
   blind player who wants the game running in the background while
   they sleep — quests ticking, sounds and music playing — without
   the voice talking at them every five minutes. Narration stays on
   by default.

The toggles are independent: any combination works (sound + no
visuals, visuals + no narration, both on, both off). Turning
narration off never turns the sound effects, music, or ambience
loops off — those keep playing and have their own settings already.

## Sequencing

Future phase, after the current work (Healing, quest-level growth,
fighter switching, tag team). Not started.

## Open questions (not answered)

1. How many poses per creature — just standing/attack/hurt/defeated,
   or more (dodge, special ability, win celebration)?
2. One picture set per creature (10 creatures now, more later) or
   shared poses with per-creature colours?
3. Health bar style — plain bars, or numbers alongside?
4. Who checks the pictures look right? Makenna is blind; Josh is
   blind too — a sighted friend would need to look at them, or Maren
   describes them.
