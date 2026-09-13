# Days at Three Branches agent

Edit `agent.py` to give every one of your villagers a routine. The platform runs a separate `Agent` instance for each NPC, so instances do not share variables or memory. The supplied `sandbox/` directory contains the local runner, types, and village helpers. Leave it unchanged, and leave `requirements.in` and `requirements.txt` alone: the pinned packages match the server.

Start with the [Getting Started guide](https://vox-deorum.github.io/game-sandbox/students/getting-started/). Then run these commands from this folder:

```console
python -m sandbox watch  # watch your villagers and the scripted visitor
python -m sandbox test   # run the checks
python -m sandbox eval   # run repeatable automated days
```

## Files you will use

| Path | Purpose |
| --- | --- |
| `agent.py` | Your `Agent` implementation and starter TODOs. |
| `environment.md` | Rules, helpers, observations, and local commands. |
| `manifest.json` | Tells Game Sandbox where the agent class lives. |
| `season.json` | Optional local season settings downloaded from My Submissions. |
| `tests/` | Checks your submission should pass. |
| `sandbox/` | Local game, helpers, and types. Do not edit it. |
| `requirements.txt` | Exact Python package versions used by the server. |
| `requirements-dev.txt` | Test dependencies. |
| `.env.example` | Example local LLM settings. |

The starter shows `action.walk`, `action.stand`, an emote, and `use`. Read [`environment.md`](environment.md) before changing it. Begin with one behavior that you can recognize in `watch`, then make it more responsive to the people and props it sees.

Chat is optional. If you add `chat(self, inbox)` to your agent, send and receive raw message dictionaries that use canonical player IDs such as `"player_0"` and `"player_1"`. For example, return `[{"to": "player_0", "text": "Hello."}]` to send a direct message. The village helpers do not include a chat namespace. Read [`environment.md`](environment.md#chat-with-other-agents) for the inbox format, broadcasts, and delivery timing.

In `watch` and `eval`, your `Agent` controls the whole cast, and `scripted_visitor` controls the visitor. The `naive` built-in is the simple baseline for the cast. When you are ready to submit, follow the [submitting guide](https://vox-deorum.github.io/game-sandbox/students/submitting/).

## Design Goal
Season 1: The goal of this season was to have the characters move around, perform tasks, and live a lively village life while interacting with the player. The characters wake up, wander around, perform tasks, greet each other and the player, react, prioritize, and go back home to sleep. 

## Reflection
Season 1: I considered techniques of partly set behavior mixed with randomized decisions, reactions to characters, random emotes and tasks of their own, a collective task to bring characters together, and a starter for random personalities. For the partly set behavior part, I needed to spend more time adding basic pathfinding, as the characters were unable to leave their houses, and as a trade-off, the movement feels a little more intentional rather than natural. As for reactions to characters, they unintentionally behave differently toward the character, which is natural. However, I also used the vision vs. hearing cone to decide whether they should greet or get startled, which seems right. I also had them prioritise greeting occasionally over tasks, which works for the most part except in timed tasks. Giving them a daily task helped me test, and then they perform random tasks based on personality; responding to the bell makes it seem like a community, and they return to sleep at the end. All these choices were made to make them seem like they had both routine and randomness in their day as feels natural. 

## AI Use Disclosure and Reflection
I used Claude Code in VS Code. It coded all of this based on my pseudocode and instructions. I verified each set of code it wrote before approving it, reverted and asked for changes as needed, tested by watching and eval, and discussed my ideas for solutions before committing to one. I did not write any code directly, but read through it to check it. It was interesting to ask it not to come up with solutions but rather to verify mine and work from there. Sometimes it got things wrong, and a few times when I switched to Haiku, it disregarded my questions and had a bit of an ego(lol). I think I need to learn to simplify my instructions or come up with another solution because it overcomplicated some very simple solutions. But other than that, I had it set to ask for approval before committing anything, and that worked especially during testing and understanding what code was being changed. 
