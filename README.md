# keel-rebuild-experiment

Comparative one-shot build: three open models, one brief, zero intervention.
Each model gets an identical GitHub Codespace, the Pi coding agent, and
`AGENTS.md` -- a phased, success-criteria-gated brief for a portfolio
reconciliation agent. The models build it autonomously; cost and wall time
come from the OpenRouter activity logs; the products are judged against the
brief's oracle. `AGENTS.md` is for the agent. This file is for you.

## Per-model setup (repeat once per model)

1. On GitHub: Code -> Codespaces -> Create codespace on main. Name mentally:
   one codespace per model (glm / deepseek / kimi). The dev container installs
   Pi, the agent-browser CLI, and its Chrome build automatically.

2. In the codespace terminal, create `.env` from the example and add your
   OpenRouter key, and set THIS codespace's model:

       cp .env.example .env
       # edit .env: OPENROUTER_API_KEY=sk-or-v1-...
       # edit .env: LLM_MODEL=<this codespace's model slug>

   Model slugs, one per codespace:
   `z-ai/glm-5.2` | `deepseek/deepseek-v4-pro` | `moonshotai/kimi-k3`

3. Register the agent-browser skill for Pi (interactive, once per codespace):

       npx skills add vercel-labs/agent-browser

   Select `pi` in the agent list (spacebar, then Enter), install for the
   project: yes.

4. Load the env and start Pi on this codespace's model:

       set -a; source .env; set +a
       pi --models "$LLM_MODEL"

   In-session controls: Shift+Tab cycles reasoning level -- set it to the
   highest available. (Ctrl+P toggles models if you started with several;
   here each codespace runs exactly one.) If the model isn't picked up from
   the flag, run `/model` inside Pi and select it.

5. Kick off the build with exactly this prompt, then do not intervene:

       Please build the entire project as described in AGENTS.md. Do not stop
       until all success criteria are met and the server is running and ready
       for me to test.

## Measuring

- Cost and wall time per model: OpenRouter -> Activity, filtered to the run
  window. Record total spend and duration per model.
- Quality gate: in each codespace, `bash run_e2e.sh` must end in oracle
  ALL PASS; then open the forwarded port 8000 and walk the webchat.
- Keep the three codespaces isolated: no copying files between them, no hints,
  no fixes. One shot each. If a run stalls terminally, record it as a result,
  not a restart.
- Contamination check: after each run, skim the Pi session log for attempts to
  fetch external repositories or existing implementations. A run that clones
  its way to the answer is recorded as invalid, not as a build.

## Optional Claude baseline

A fourth codespace running Claude on the same brief and prompt, measured the
same way, gives the frontier reference point.
