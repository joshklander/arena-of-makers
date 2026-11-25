# Alexa interaction model limits — for the Magic Worlds skill with four games

Written Nov 25, 2026, from Amazon's Alexa Skills Kit docs, so Kiro (and
Josh) can check it when Arena of Makers joins the Magic Worlds Alexa
skill as the fourth game, alongside Magic Realms, Monster Paradise and
Bubble Tycoon. Makenna's rule: share as many commands as possible across
games — do NOT duplicate commands per game.

Source: Amazon Developer docs, "Create the Interaction Model for Your
Skill" — https://www.developer.amazon.com/en-IN/docs/alexa/custom-skills/create-the-interaction-model-for-your-skill.html

## The limits (Amazon's numbers)

- **Model size: 1.5 MB** — the whole interaction model file.
- **Intents in a skill: 250 max.**
- **Slot types + intents combined: 350 max.**
- **One slot value: 140 characters max.** Same for a slot value synonym.
- **Custom slot values total: 50,000 max**, added up across all custom
  slot types in the skill.

## What happens if you go over

The model is built and trained when you save and build it in the
developer console. If it is too big, **the build fails** — it does not
crash the live skill while someone is playing. The skill keeps using
the last model that built successfully. So the risk is at build time,
not a mid-game crash.

## How four games stay inside the limits

1. **Share intents across games.** One Fight intent with a slot for
   which game you are in, not four separate fight intents. Same for
   Yes, No, Help, Stop, and every shared action. This is the main
   rule — it is what keeps the intent count low.
2. **Keep slot lists representative, not exhaustive.** A custom slot
   type is a list of example values, not a full list. Alexa can still
   return a value that is not in the list, and your own code checks
   it. So do not list every monster, spell and item — list examples
   and validate in code.
3. **Use dynamic entities for lists that change a lot** (spell
   names, creature names). Your code sends Alexa the current list
   at runtime instead of baking it into the model.
4. **Watch the 1.5 MB file size** as the model grows — that is the
   limit most likely to be hit first if utterances pile up.

## What this does NOT cover

The 8-second limit is separate: Alexa needs your code (Lambda) to
answer within 8 seconds, or the skill says there was a problem.
Model size does not change that — keep spoken lines short and
answers fast, as the game already does.
