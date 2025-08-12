import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from openai import OpenAI
import tiktoken
from typing import List, Dict, Any, Optional, Tuple, Set
import threading
import re
import json

# --- GUI Layout Constants ---
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 861

CHAT_DISPLAY_X = 10
CHAT_DISPLAY_Y = 10
CHAT_DISPLAY_WIDTH = WINDOW_WIDTH - 20
CHAT_DISPLAY_HEIGHT = WINDOW_HEIGHT - 100  # slightly shorter to make room for the Sources button row

INPUT_X = 10
INPUT_Y = WINDOW_HEIGHT - 70
INPUT_WIDTH = WINDOW_WIDTH - 190
INPUT_HEIGHT = 25

BUTTON_X = WINDOW_WIDTH - 170
BUTTON_Y = WINDOW_HEIGHT - 70
BUTTON_WIDTH = 70
BUTTON_HEIGHT = 25

SOURCES_BUTTON_X = WINDOW_WIDTH - 90
SOURCES_BUTTON_Y = WINDOW_HEIGHT - 70
SOURCES_BUTTON_WIDTH = 80
SOURCES_BUTTON_HEIGHT = 25

SEND_BTN_LABEL = "Send"
SRC_BTN_LABEL = "Show sources"

# Toggle if you want the hosted search disabled
ENABLE_HOSTED_WEB_SEARCH = True

URL_REGEX = re.compile(
    r"(https?://[^\s)]+)",
    re.IGNORECASE
)

def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen: Set[str] = set()
    out: List[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out

class ChatMemoryBot:
    def __init__(self, system_prompt: str, model: str = "gpt-5", max_tokens: int = 20000):
        self.client = OpenAI()
        self.model = model
        self.max_tokens = max_tokens

        # tiktoken mapping with a safe fallback for new model names
        try:
            self.encoder = tiktoken.encoding_for_model(model)
        except KeyError:
            prefers_long_ctx = any(s in model for s in ("gpt-5", "4.1", "4o", "o4", "o3", "200k"))
            encoding_name = "o200k_base" if prefers_long_ctx else "cl100k_base"
            self.encoder = tiktoken.get_encoding(encoding_name)

        self.chat_history: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        print(self.chat_history)

    def _count_tokens(self, messages: List[Dict[str, str]]) -> int:
        return sum(len(self.encoder.encode(msg.get("content", ""))) for msg in messages)

    def _summarize_history(self, old_messages: List[Dict[str, str]]) -> str:
        summary_prompt: List[Dict[str, str]] = [
            {"role": "system", "content": "Summarize the following chat history in ~300 words, neutral tone."}
        ] + old_messages

        resp = self.client.responses.create(
            model=self.model,
            input=summary_prompt,
        )
        return getattr(resp, "output_text", "") or ""

    def _trim_history_if_needed(self):
        token_count = self._count_tokens(self.chat_history)
        print(f"\nTOKEN COUNT = {token_count}")
        if token_count > self.max_tokens:
            system_msg = self.chat_history[0]
            old_messages = self.chat_history[1:-10]
            recent_messages = self.chat_history[-10:]
            print(f"\nTRIMMING HISTORY: {len(old_messages)} messages summarized to 1 message")
            summary = self._summarize_history(old_messages)
            print(f"\nSUMMARY START:\n{summary}\nSUMMARY END***")
            print(f"\nSUMMARY LENGTH (chars): {len(summary)}\n")
            self.chat_history = [
                system_msg,
                {"role": "assistant", "content": f"Summary of earlier conversation: {summary}"}
            ] + recent_messages

    # --- Robust citation extraction ---
    def _extract_citations(self, resp: Any, reply_text: str) -> List[str]:
        urls: List[str] = []

        # 1) Best effort: walk the structured response for any fields that look like citations/urls.
        def walk(obj: Any):
            if isinstance(obj, dict):
                # Common places: "url", "source", "href"
                for k, v in obj.items():
                    if k.lower() in ("url", "source", "href") and isinstance(v, str) and v.startswith(("http://", "https://")):
                        urls.append(v.strip())
                    walk(v)
            elif isinstance(obj, list):
                for it in obj:
                    walk(it)
            # primitives ignored

        try:
            # Convert to vanilla Python (in case it's a pydantic-like object)
            # If resp is already dict-like, json.dumps/loads is safe; otherwise getattr fallback.
            raw = json.loads(json.dumps(resp, default=lambda o: getattr(o, "__dict__", str(o))))
            walk(raw)
        except Exception as e:
            print(f"[Citations] Structured parse fallback due to: {type(e).__name__}: {e}")

        # 2) Fallback: extract URLs present in the final text.
        urls += URL_REGEX.findall(reply_text or "")

        # Clean + de-dupe + small normalization
        cleaned = []
        for u in urls:
            # strip trailing punctuation that often follows links in prose
            u = u.rstrip(").,;:]").lstrip("([")
            cleaned.append(u)

        return _dedupe_preserve_order(cleaned)

    def ask(self, user_input: str) -> Tuple[str, List[str]]:
        print("\nASKING AI")
        self.chat_history.append({"role": "user", "content": user_input})
        self._trim_history_if_needed()

        request_kwargs: Dict[str, Any] = {
            "model": self.model,
            "input": self.chat_history
        }
        if ENABLE_HOSTED_WEB_SEARCH:
            request_kwargs["tools"] = [{"type": "web_search"}]
            request_kwargs["tool_choice"] = "auto"

        resp = self.client.responses.create(**request_kwargs)

        reply = getattr(resp, "output_text", "") or ""
        sources = self._extract_citations(resp, reply)

        self.chat_history.append({"role": "assistant", "content": reply})
        print("\n".join(f"{idx:02d}: {msg}" for idx, msg in enumerate(self.chat_history, 1)))
        return reply, sources


class ChatbotApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title("OpenAI API (Responses) — Web-enabled Chatbot")

        str_system_prompt = (
            "You are speaking to TechBot, an expert AI assistant specializing in programming, "
            "software engineering, mathematics, physics and technology. Provide clear, concise "
            "and accurate technical answers. If code is requested, use best practices and explain "
            "your reasoning when appropriate. If you are asked for a numerical calculation then "
            "just provide the number without any explanation."
        )

        self.bot = ChatMemoryBot(system_prompt=str_system_prompt)
        self.last_sources: List[str] = []  # stores sources for the most recent bot message

        self.chat_display = ScrolledText(master, wrap=tk.WORD, state='disabled')
        self.chat_display.place(x=CHAT_DISPLAY_X, y=CHAT_DISPLAY_Y,
                                width=CHAT_DISPLAY_WIDTH, height=CHAT_DISPLAY_HEIGHT)

        self.user_input = tk.Entry(master)
        self.user_input.place(x=INPUT_X, y=INPUT_Y, width=INPUT_WIDTH, height=INPUT_HEIGHT)
        self.user_input.bind("<Return>", self.send_message)

        self.send_button = tk.Button(master, text=SEND_BTN_LABEL, command=lambda: self.send_message())
        self.send_button.place(x=BUTTON_X, y=BUTTON_Y, width=BUTTON_WIDTH, height=BUTTON_HEIGHT)

        self.src_button = tk.Button(master, text=SRC_BTN_LABEL, command=self.show_sources)
        self.src_button.place(x=SOURCES_BUTTON_X, y=SOURCES_BUTTON_Y, width=SOURCES_BUTTON_WIDTH, height=SOURCES_BUTTON_HEIGHT)

    def send_message(self, _: Optional[Any] = None) -> None:
        user_text = self.user_input.get().strip()
        if not user_text:
            return
        self.display_message("You", user_text)
        self.user_input.delete(0, tk.END)
        threading.Thread(target=self.get_bot_response, args=(user_text,), daemon=True).start()

    def get_bot_response(self, user_text: str):
        try:
            reply, sources = self.bot.ask(user_text)
            self.last_sources = sources or []
        except Exception as e:
            reply = f"[Error] {type(e).__name__}: {e}"
            self.last_sources = []
        self.display_message("Bot", reply)

    def display_message(self, sender: str, message: str) -> None:
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, f"{sender}: {message}\n\n")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)

    def show_sources(self) -> None:
        self.chat_display.configure(state='normal')
        if not self.last_sources:
            self.chat_display.insert(tk.END, "Sources: (none detected)\n\n")
        else:
            self.chat_display.insert(tk.END, "Sources:\n",)
            for i, src in enumerate(self.last_sources, 1):
                self.chat_display.insert(tk.END, f"  {i}. {src}\n")
            self.chat_display.insert(tk.END, "\n")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+0+0")
    root.resizable(False, False)
    ChatbotApp(root)
    root.mainloop()
