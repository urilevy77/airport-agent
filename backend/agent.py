#!/usr/bin/env python3
"""
agent.py — Airport Investment Intelligence Agent: the conversation loop.

The model reads the question, decides which signal to ACTIVATE (tool-calling), the
signal runs against BTS r495-tyji, and the model writes the answer.

This file owns ONLY the loop and the memory. The other pieces live next door:
    tools.py    the five tools + their schemas  (what the agent can DO)
    prompts.py  the system prompt              (how the agent BEHAVES)
    llm.py      the model provider              (WHO answers, and in what shape)

SETUP   pip install anthropic
        export ANTHROPIC_API_KEY=...       # and optionally ANTHROPIC_MODEL
RUN     python3 agent.py "Compare LA and Santa Ana congestion"
        python3 agent.py                    # interactive
"""
import json
import sys

from llm import Client
from prompts import system_prompt
from tools import TOOL_SCHEMAS, TOOLS

# ---------- MEMORY: a list of dicts, resent in full on every call ----------
MAX_MESSAGES = 40        # kept after the system prompt; ~10 tool-using turns
MAX_ROUNDS = 5           # tool-calling rounds per question

def call_tool(call):
    """Run one tool the model asked for; return its result as a JSON string.

    The guard is deliberate: a bad IATA code or a BTS outage becomes an
    {"error": ...} the model can read and recover from, instead of killing
    the conversation and losing all history.
    """
    function = call["function"]
    try:
        result = TOOLS[function["name"]](**json.loads(function["arguments"]))
    except Exception as e:
        result = {"error": f"{type(e).__name__}: {e}"}
    return json.dumps(result)

class Conversation:
    """Holds the conversation as self.messages — a growing list of dicts.

    The API is stateless: it remembers nothing between calls. What makes this a
    conversation is that we resend the ENTIRE list every time, so the model can
    re-read earlier turns and resolve follow-ups like "and Boston?".
    """

    def __init__(self, model=None):
        self.client = Client(model)
        self.model = self.client.model
        # Built here, not imported as a constant: the prompt states today's date
        # and how stale the table is, and a Conversation is constructed per
        # request (server/app.py), which is what keeps both fresh.
        self.messages = [{"role": "system", "content": system_prompt()}]

    def say(self, role, content, **extra):
        """Append one message to memory."""
        self.messages.append({"role": role, "content": content, **extra})

    def ask(self, question):
        self.say("user", question)
        for _ in range(MAX_ROUNDS):
            msg = self._next_message()
            calls = msg.get("tool_calls")
            if not calls:
                self.trim()                  # only safe once the turn has settled
                return msg["content"]
            for call in calls:
                self.say("tool", call_tool(call), tool_call_id=call["id"])
        return "Stopped after too many tool rounds."

    def _next_message(self):
        """One model call. llm.py hands back a plain dict, so self.messages
        stays uniformly JSON-serialisable — that is what lets the whole history
        round-trip through the browser and back."""
        message = self.client.complete(
            system=self.messages[0]["content"],   # the system prompt is not a message
            messages=self.messages[1:],
            tools=TOOL_SCHEMAS)
        self.messages.append(message)
        return message

    def trim(self):
        """Drop oldest messages, keeping the system prompt.

        A 'tool' message is only valid right after the assistant message holding
        its tool_call_id, so never leave one at the front — that's a 400 from the
        API. Walk forward past any orphaned tool results.
        """
        system, rest = self.messages[0], self.messages[1:]
        if len(rest) <= MAX_MESSAGES:
            return
        kept = rest[-MAX_MESSAGES:]
        while kept and kept[0]["role"] == "tool":
            kept.pop(0)
        self.messages = [system] + kept

    def save(self, path):
        """Write the whole conversation to disk — possible because every
        message is a plain dict. Load it back with json.load into .messages."""
        with open(path, "w") as fh:
            json.dump(self.messages, fh, indent=1)

def run(question):
    """One-shot ask — unchanged behaviour for scripted use."""
    return Conversation().ask(question)

QUIT = {"exit", "quit"}

def prompt():
    """Read one line. Returns None on Ctrl-C / Ctrl-D / exit — the guard is
    what turns those into a clean goodbye instead of a traceback."""
    try:
        line = input("you > ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    return None if line.lower() in QUIT else line

def repl():
    convo = Conversation()
    print(f"Airport agent ({convo.model}) — follow-ups keep context.")
    print("  reset = clear memory   save = write history.json   exit = quit\n")
    while (q := prompt()) is not None:
        if not q:
            continue
        if q.lower() == "reset":
            convo = Conversation(convo.model)
            print("[memory cleared]\n")
        elif q.lower() == "save":
            convo.save("history.json")
            print(f"[saved {len(convo.messages)} messages to history.json]\n")
        else:
            print(f"\n{convo.ask(q)}\n")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        print(run(" ".join(sys.argv[1:])))   # one-shot, as before
    else:
        repl()                               # conversational
