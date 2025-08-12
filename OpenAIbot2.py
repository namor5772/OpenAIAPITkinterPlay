import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from openai import OpenAI
import tiktoken
from typing import List, Dict, Any, Optional
import threading

# --- GUI Layout Constants ---
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 861

CHAT_DISPLAY_X = 10
CHAT_DISPLAY_Y = 10
CHAT_DISPLAY_WIDTH = WINDOW_WIDTH - 20
CHAT_DISPLAY_HEIGHT = WINDOW_HEIGHT - 60

INPUT_X = 10
INPUT_Y = WINDOW_HEIGHT - 40
INPUT_WIDTH = WINDOW_WIDTH - 100
INPUT_HEIGHT = 25

BUTTON_X = WINDOW_WIDTH - 80
BUTTON_Y = WINDOW_HEIGHT - 40
BUTTON_WIDTH = 70
BUTTON_HEIGHT = 25

# Toggle this if you want to disable hosted search for any reason
ENABLE_HOSTED_WEB_SEARCH = True

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
        # Approximate token count for trimming logic
        return sum(len(self.encoder.encode(msg["content"])) for msg in messages if "content" in msg)

    def _summarize_history(self, old_messages: List[Dict[str, str]]) -> str:
        # Use Responses API to summarise old messages into a single assistant summary
        summary_prompt: List[Dict[str, str]] = [
            {"role": "system", "content": "Summarize the following chat history in ~300 words, neutral tone."}
        ] + old_messages

        resp = self.client.responses.create(
            model=self.model,
            input=summary_prompt,  # same role/content shape as chat
            # No tools needed for the summary call
        )
        return resp.output_text or ""

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

    def ask(self, user_input: str) -> str:
        print("\nASKING AI")
        self.chat_history.append({"role": "user", "content": user_input})
        self._trim_history_if_needed()

        # Build the request to Responses API, reusing the full chat history
        request_kwargs: Dict[str, Any] = {
            "model": self.model,
            "input": self.chat_history
        }
        if ENABLE_HOSTED_WEB_SEARCH:
            request_kwargs["tools"] = [{"type": "web_search"}]
            request_kwargs["tool_choice"] = "auto"  # let the model decide to search or not

        resp = self.client.responses.create(**request_kwargs)

        # The Responses API provides a convenience property for the final text
        reply = resp.output_text or ""
        self.chat_history.append({"role": "assistant", "content": reply})
        print("\n".join(f"{idx:02d}: {msg}" for idx, msg in enumerate(self.chat_history, 1)))
        return reply

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

        self.chat_display = ScrolledText(master, wrap=tk.WORD, state='disabled')
        self.chat_display.place(x=CHAT_DISPLAY_X, y=CHAT_DISPLAY_Y,
                                width=CHAT_DISPLAY_WIDTH, height=CHAT_DISPLAY_HEIGHT)

        self.user_input = tk.Entry(master)
        self.user_input.place(x=INPUT_X, y=INPUT_Y, width=INPUT_WIDTH, height=INPUT_HEIGHT)
        self.user_input.bind("<Return>", self.send_message)

        self.send_button = tk.Button(master, text="Send", command=lambda: self.send_message())
        self.send_button.place(x=BUTTON_X, y=BUTTON_Y, width=BUTTON_WIDTH, height=BUTTON_HEIGHT)

    def send_message(self, _: Optional[Any] = None) -> None:
        user_text = self.user_input.get().strip()
        if not user_text:
            return
        self.display_message("You", user_text)
        self.user_input.delete(0, tk.END)
        threading.Thread(target=self.get_bot_response, args=(user_text,), daemon=True).start()

    def get_bot_response(self, user_text: str):
        try:
            reply = self.bot.ask(user_text)
        except Exception as e:
            reply = f"[Error] {type(e).__name__}: {e}"
        self.display_message("Bot", reply)

    def display_message(self, sender: str, message: str) -> None:
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, f"{sender}: {message}\n\n")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+0+0")
    root.resizable(False, False)
    ChatbotApp(root)
    root.mainloop()
