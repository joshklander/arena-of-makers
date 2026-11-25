# Linking Supabase and DynamoDB — sync design (proposal for Kiro)

Written Nov 25, 2026, for Kiro to review. Makenna's idea: keep Supabase
and DynamoDB linked together, so no matter whether she works with Maren
on Supabase or with Kiro on DynamoDB and AWS, the project stays up
either way — no manual conversion every time.

## The goal

Work in either place, and both sides see every change. Supabase stays
the workspace for building (PC game, migrations on GitHub main).
DynamoDB is where the Alexa skill reads. Changes flow both ways,
automatically, within seconds.

## How it works, step by step

1. **Every change gets a stamp.** What changed, when it changed, and
   where it came from (Supabase or DynamoDB).
2. **Each side has a watcher.** Supabase is Postgres underneath: its
   write-ahead log records every insert, update and delete, and a
   change-data-capture reader (or a Supabase database webhook) sends
   each change out. DynamoDB has DynamoDB Streams: every item change
   goes into a stream, and a small AWS Lambda function reads it.
3. **The watcher copies the change across.** A change in Supabase is
   written into DynamoDB by a Lambda; a change in DynamoDB is written
   into Supabase by a Lambda. Usually within seconds — not instant,
   but close.
4. **Loop guard.** A change copied across is stamped "this came from
   the sync." When the other side's watcher sees that stamp, it does
   not send it back. Without this, the two sides would copy each
   other forever.
5. **Mapping.** Postgres rows and DynamoDB items are different
   shapes. One player row becomes one DynamoDB item. That mapping is
   a one-time job, not something redone at each publish.

## The tie-breaker rule — Makenna's proposal, for Kiro to agree or change

**Whoever made the change first wins.** If the same thing is changed
on both sides at the same time, the first change made is the one that
sticks, and the later conflicting change is discarded.

Kiro: please say whether you agree with first-write-wins, or whether
you would rather use last-write-wins (the later change wins), or field
ownership (game rules only ever change in Supabase, player progress
only ever changes in DynamoDB, so they can never fight over the same
field), or whether you think we should skip the link and just do the
full migration to DynamoDB instead.

## The honest catch

Two-way sync is the hard version. One-way (Supabase to DynamoDB only)
is easy and safe. Two-way needs the stamp, the loop guard, and the
tie-breaker above, plus testing for: the same field changed on both
sides at once, a change made while one side is offline, and a schema
change (a new column or field needs a new mapping). Whoever builds the
two watcher Lambdas needs to test those cases before players depend
on it.

## Alternative

Full migration: move everything to DynamoDB once, and stop using
Supabase. Simpler in the long run, but a bigger one-time job, and the
PC game would need to talk to DynamoDB instead of Supabase.
