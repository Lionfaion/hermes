#!/usr/bin/env python3
"""
Hermes CLI — interactive assistant over SSH.
Usage: python interface/cli.py
"""
import sys
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from assistant import HermesAssistant
from inference_client import is_online, list_models
from config import ASSISTANT_NAME, OLLAMA_MODEL

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

_COMMANDS = {
    "/help":    "Show this command list",
    "/clear":   "Clear conversation memory for this session",
    "/new":     "Start a brand-new session",
    "/status":  "Check GPU node availability",
    "/models":  "List models available on the GPU node",
    "/exit":    "Quit",
}

BANNER = f"""
{'─' * 52}
  {ASSISTANT_NAME}  │  Home AI Assistant
  Model  : {OLLAMA_MODEL}
  Type /help for commands, Ctrl+C to quit
{'─' * 52}"""


def print_help() -> None:
    print("\nCommands:")
    for cmd, desc in _COMMANDS.items():
        print(f"  {cmd:<10}  {desc}")
    print()


def main() -> None:
    print(BANNER)
    gpu_status = "ONLINE" if is_online() else "OFFLINE"
    print(f"  GPU node : {gpu_status}\n")

    assistant = HermesAssistant()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        if user_input == "/help":
            print_help()
        elif user_input == "/clear":
            assistant.clear_memory()
            print("Memory cleared.\n")
        elif user_input == "/new":
            sid = assistant.new_session()
            print(f"New session started.\n")
        elif user_input == "/status":
            status = "ONLINE" if is_online() else "OFFLINE"
            print(f"GPU node: {status}\n")
        elif user_input == "/models":
            models = list_models()
            if models:
                print("Available models:")
                for m in models:
                    print(f"  • {m}")
            else:
                print("No models found or GPU node offline")
            print()
        elif user_input in ("/exit", "exit", "quit"):
            print("Goodbye.")
            break
        else:
            print(f"\n{ASSISTANT_NAME}: ", end="", flush=True)
            for chunk in assistant.respond_stream(user_input):
                print(chunk, end="", flush=True)
            print("\n")


if __name__ == "__main__":
    main()
