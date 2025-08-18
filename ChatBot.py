import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText
from openai import OpenAI
import tiktoken
from typing import List, Dict, Any, Optional, Tuple, Set
import threading
import re
import json

# --- GUI Layout Constants ---
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 800

MODEL_CMB_X = 10
MODEL_CMB_Y = 10
MODEL_CMB_WIDTH = 280
MODEL_CMB_HEIGHT = 25

CHAT_DISPLAY_X = 10
CHAT_DISPLAY_Y = 45
CHAT_DISPLAY_WIDTH = WINDOW_WIDTH - 20
CHAT_DISPLAY_HEIGHT = WINDOW_HEIGHT - 90  # slightly shorter to make room for the Sources button row

INPUT_X = 10
INPUT_Y = WINDOW_HEIGHT - 35
INPUT_WIDTH = WINDOW_WIDTH - 110
INPUT_HEIGHT = 25

SOURCES_BUTTON_X = WINDOW_WIDTH - 90
SOURCES_BUTTON_Y = WINDOW_HEIGHT - (35+2)
SOURCES_BUTTON_WIDTH = 80
SOURCES_BUTTON_HEIGHT = 25

SEND_BTN_LABEL = "Send"
SRC_BTN_LABEL = "Show sources"

# --- API Models related ---
ENABLE_HOSTED_WEB_SEARCH = True  # Turn this on to use the hosted web search tool
DEFAULT_MODEL = "" # Non-browsing model (or used without tools)
BROWSE_MODEL = "" # Browsing-capable model for hosted web search "gpt-4o"
MODEL_OPTIONS = []

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
    def __init__(self, system_prompt: str, max_tokens: int = 20000):
        self.client = OpenAI()

        # Get all models intended for standard completions/chat into MODEL_OPTIONS array
        global MODEL_OPTIONS, DEFAULT_MODEL, BROWSE_MODEL
        models = self.client.models.list()

        n = 0
        # Skip anything not intended for standard completions/chat
        for m in models.data:
            model_id = m.id
            if any(skip in model_id for skip in ["embedding", "audio", "search", "realtime", "preview","transcribe", "tts"]):
                continue
            if model_id.startswith("gpt-") and not("instruct" in model_id) and (model_id != "gpt-image-1"):
                MODEL_OPTIONS.append(model_id)
                n += 1

        print(f"\n=== {n} Chat Models (use /chat/completions) ===")
        n = 0
        for cm in sorted(MODEL_OPTIONS): 
            n +=1
            print(f"{n}: {cm}")

        DEFAULT_MODEL = MODEL_OPTIONS[0]
        BROWSE_MODEL = MODEL_OPTIONS[0]

        self.model = DEFAULT_MODEL
        self.browse_model = BROWSE_MODEL
        self.max_tokens = max_tokens

        # tiktoken mapping with a safe fallback for new model names
        try:
            self.encoder = tiktoken.encoding_for_model(self.browse_model)
        except KeyError:
            print("EXCEPTION")
            prefers_long_ctx = any(s in self.browse_model for s in ("gpt-5", "4.1", "4o", "o4", "o3", "200k"))
            encoding_name = "o200k_base" if prefers_long_ctx else "cl100k_base"
            self.encoder = tiktoken.get_encoding(encoding_name)

        self.chat_history: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        print(f"System prompt:\n{self.chat_history}")


    def _count_tokens(self, messages: List[Dict[str, str]]) -> int:
        return sum(len(self.encoder.encode(msg.get("content", ""))) for msg in messages)


    def _summarize_history(self, old_messages: List[Dict[str, str]]) -> str:
        """
        Use the DEFAULT (non-browsing) model for summaries to avoid any tool usage.
        """
        summary_prompt: List[Dict[str, str]] = [
            {"role": "system", "content": "Summarize the following chat history in ~500 words, neutral tone."}
        ] + old_messages

        resp = self.client.responses.create(
            model=self.model,  # default model; no tools
            input=summary_prompt, # type: ignore
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

            # this is the new trimmed chat history
            self.chat_history = [
                system_msg,
                {"role": "assistant", "content": f"Summary of earlier conversation: {summary}"}
            ] + recent_messages


    # --- Robust citation extraction ---
    def _extract_citations(self, resp: Any, reply_text: str) -> List[str]:
        urls: List[str] = []

        # 1) Walk the structured response to find URL-like fields
        def walk(obj: Any):
            if isinstance(obj, dict):
                for k, v in obj.items(): # type: ignore
                    if k.lower() in ("url", "source", "href") and isinstance(v, str) and v.startswith(("http://", "https://")): # type: ignore
                        urls.append(v.strip())
                    walk(v)
            elif isinstance(obj, list):
                for it in obj: # type: ignore
                    walk(it)
            # primitives ignored

        try:
            raw = json.loads(json.dumps(resp, default=lambda o: getattr(o, "__dict__", str(o))))
            walk(raw)
        except Exception as e:
            print(f"[Citations] Structured parse fallback due to: {type(e).__name__}: {e}")

        # 2) Fallback: URLs present in the final text
        urls += URL_REGEX.findall(reply_text or "")

        # Clean + de-dupe
        cleaned = []
        for u in urls:
            u = u.rstrip(").,;:]").lstrip("([")
            cleaned.append(u) # type: ignore

        return _dedupe_preserve_order(cleaned) # type: ignore


    def _build_request(self) -> Dict[str, Any]:
        """
        Decide model and tool configuration based on ENABLE_HOSTED_WEB_SEARCH.
        Ensures tools are only sent with a browsing-capable model.
        """
        use_browsing = ENABLE_HOSTED_WEB_SEARCH
        if use_browsing:
            # Browsing flow: choose browsing model and include the hosted tool
            return {
                "model": self.browse_model,
                "input": self.chat_history,
                "tools": [{"type": "web_search"}],
                "tool_choice": "auto",
            }
        else:
            # Non-browsing flow: default model with NO tools
            return {
                "model": self.model,
                "input": self.chat_history,
            }


    def ask(self, user_input: str) -> Tuple[str, List[str]]:
        print("\nASKING AI")
        self.chat_history.append({"role": "user", "content": user_input})
        self._trim_history_if_needed()

        request_kwargs: Dict[str, Any] = self._build_request()

        # Primary attempt
        try:
            resp = self.client.responses.create(**request_kwargs) # type: ignore
        except Exception as e:
            # Graceful fallback if the error suggests tools/model incompatibility
            msg = str(e)
            if ("web_search" in msg or "web_search_preview" in msg or "tools" in msg) and "not supported" in msg.lower():
                print("[Warn] Tool/model mismatch detected. Retrying without tools on DEFAULT_MODEL.")
                fallback_kwargs = { # type: ignore
                    "model": self.model,
                    "input": self.chat_history
                }
                resp = self.client.responses.create(**fallback_kwargs) # type: ignore
            else:
                raise  # unrelated error

        reply = getattr(resp, "output_text", "") or "" # type: ignore
        sources = self._extract_citations(resp, reply)

        self.chat_history.append({"role": "assistant", "content": reply})
        print("\n".join(f"{idx:02d}: {msg}" for idx, msg in enumerate(self.chat_history, 1)))
        return reply, sources


class ChatbotApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title("OpenAI API (Responses) — Web-enabled Chatbot")

        str_system_prompt = (
            "1. You are speaking to Kenneth Mandrake, an expert AI assistant specializing in programming, "
            "   software engineering, math, physics and technology."
            "   Provide clear, concise and accurate technical answers. "
            "2. If code is requested, use best practices and explain your reasoning when appropriate."
            "3. If you are asked for a numerical calculation then just provide the number without explanations."
            "4. In replies where the word math is used, replace it with the word maths or mathematics "
            "   depending on the formality of the response."
        )


        self.bot = ChatMemoryBot(system_prompt=str_system_prompt)
        self.last_sources: List[str] = []  # stores sources for the most recent bot message



        # 2) Model picker — labels mapped to backend model IDs

        global MODEL_OPTIONS
        self.labels = MODEL_OPTIONS
            
        initial_label = MODEL_OPTIONS[0]
        self.model_var = tk.StringVar(master, value=initial_label)
        self.model_cmb = ttk.Combobox(master, state="readonly", values=self.labels, textvariable=self.model_var)
        self.model_cmb.place(x=MODEL_CMB_X, y=MODEL_CMB_Y, width=MODEL_CMB_WIDTH, height=MODEL_CMB_HEIGHT)

        self.chat_display = ScrolledText(master, wrap=tk.WORD, state='disabled', bg="lightgray")
        self.chat_display.place(x=CHAT_DISPLAY_X, y=CHAT_DISPLAY_Y, width=CHAT_DISPLAY_WIDTH, height=CHAT_DISPLAY_HEIGHT)

        self.user_input = tk.Entry(master, bg="lightgray")
        self.user_input.place(x=INPUT_X, y=INPUT_Y, width=INPUT_WIDTH, height=INPUT_HEIGHT)
        self.user_input.bind("<Return>", self.send_message)

        self.src_button = tk.Button(master, text=SRC_BTN_LABEL, command=self.show_sources)
        self.src_button.place(x=SOURCES_BUTTON_X, y=SOURCES_BUTTON_Y, width=SOURCES_BUTTON_WIDTH, height=SOURCES_BUTTON_HEIGHT)


    def send_message(self, _: Optional[Any] = None) -> None:
        user_text = self.user_input.get().strip()
        if not user_text: return
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
            self.chat_display.insert(tk.END, "Sources:\n")
            for i, src in enumerate(self.last_sources, 1):
                self.chat_display.insert(tk.END, f"  {i}. {src}\n")
            self.chat_display.insert(tk.END, "\n")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)


if __name__ == "__main__":
    root = tk.Tk()
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+0+0")
    root.resizable(False, False)
    app = ChatbotApp(root)
    root.mainloop()
