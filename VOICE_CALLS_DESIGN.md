# Voice calls (group + private) — design draft (Makenna, 2026-11-18)

Status: PROPOSAL ONLY. Not coded, not pushed. To build in its own phase,
after Phase 23 (quest levels). First milestone: a working 1:1 call between
Makenna and Josh; group calls after that works.

## What it is

- Private (1:1) audio calls and group audio calls between players, inside
  the game.
- Supabase does the setup (signalling): ringing, accept/decline, who joins,
  who is in a call — via Supabase Realtime (broadcast/presence), the part
  of Supabase the game already uses. Supabase does NOT carry voice audio.
- The voice audio goes through a media server (SFU). Each player sends
  their voice once to the server; the server forwards it to everyone else
  in the call (selective forwarding — it forwards, it does not mix).
- Service choice: **LiveKit**. Its Cloud Build plan is $0/month with
  5,000 WebRTC participant-minutes/month + 50 GB transfer, no credit card
  needed (older pages list 10,000 minutes — the 5,000 figure is the
  current Build plan; verify on LiveKit's pricing page before budgeting).
  LiveKit's server is also open source (Apache 2.0), so self-hosting has
  no licence fee, only server/bandwidth. Alternatives checked Nov 18,
  2026: Daily.co (10,000 free minutes/month, then $0.004/min video or
  $0.00099/min audio-only) and Cloudflare Realtime SFU (first 1,000 GB
  egress/month free, then $0.05/GB). Daily is a poor fit for this game:
  its Python SDK has no Windows wheels. Scale example: Makenna + Josh
  talking 1 hour a day = about 3,600 participant-minutes a month, inside
  all three free tiers.
- Python fit (checked Nov 18, 2026): LiveKit has an official Python
  client SDK (`livekit` on PyPI, `livekit.rtc.Room`, `MediaDevices` for
  mic/speakers built on sounddevice, with echo cancellation, noise
  suppression and volume control built in, wheels for Windows x64, macOS
  and Linux, Python 3.9–3.14). That is the kit to use.
- No Muse connector exists for LiveKit, Daily, or Cloudflare Realtime
  (checked Nov 18, 2026). The game talks to the service directly with its
  own key — the key lives on each player's own computer, like the
  Supabase key, never in chat and never bundled into the exe.

## Hard parts (honest list)

- Mixing LiveKit's asyncio code with the game's wxPython event loop.
- Microphone/speaker behaviour on different players' Windows computers.
- NAT/TURN (LiveKit Cloud includes TURN).
- Join tokens minted server-side, so the LiveKit API secret never ships
  in the game — same anti-cheat rule as everything else.
- Who can call whom, mute, block — safety, friends-only to start.
- Packaging the native LiveKit wheels into the PyInstaller exe.
- Maren can help with the code (server functions, game UI, tests, in
  phases). Makenna/Josh create the LiveKit account and keep its keys
  local; the real proof is a live call between two computers.

## FREE-TIER GUARD — DECIDED by Makenna, Nov 18, 2026 (hard requirement)

When the free tier allowance is used up, the game must NOT allow any
voice calls — no group calls, no private calls, nothing. Reasons, in her
words (substance): no errors, and nothing popping up on people's
accounts asking for somebody's credit card in the app.

How it must work:

- The game tracks call minutes itself, server-side, in Supabase — it
  does NOT trust the media service to stop calls, and it does NOT rely
  on the service's own cap as the only protection. A server record
  (table or settings row) holds the monthly voice-minute budget and how
  many minutes have been used this month.
- Every call logs its start and end (server-side, on hang-up and on
  disconnect), and the server adds the minutes to the month's total.
- Before ANY call starts — private or group — the game asks the server
  for a join token, and the server checks the budget FIRST. If the
  month's minutes are used up, the server refuses the token and the game
  says so in plain words, e.g. "Voice calls are paused until next month
  — the free call minutes are used up." No call starts, no error
  message, no payment page, no credit card prompt, ever, in the app.
- If the budget runs out DURING a call, the call ends gracefully with a
  spoken plain-words message ("The free call minutes are used up, so
  this call is ending — calls will be back next month."), not an error
  and not a cut-off mid-word without explanation.
- The budget number is a setting in ONE place on the server (set from
  the LiveKit plan — 5,000 minutes/month on the Build plan), so if the
  plan ever changes, the number changes there and nowhere else.
- The game NEVER opens a payment page or asks for a card. If more
  minutes are ever wanted, that is a separate decision by Makenna/Josh
  outside the game — the game itself only ever says calls are paused.
- The call screen shows how many free call minutes are left this month
  (or says calls are paused), so nobody is surprised.
- Suggested, not decided: a warning when the budget is nearly used up
  (e.g. at 80%), spoken once, so the pause does not come out of nowhere.

## Questions for Makenna (not answered yet)

1. Who can call whom to start — friends only, or any player by code?
2. Warning at 80% of the budget — yes or no?
3. Should a call that is running when the month turns over keep going,
   or end and need a new call?
