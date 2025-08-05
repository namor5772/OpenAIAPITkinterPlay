import tkinter as tk 
from tkinter.scrolledtext import ScrolledText
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
import tiktoken
from typing import List, Dict, Any, Optional
import threading

# --- GUI Layout Constants ---
WINDOW_WIDTH = 800 #600
WINDOW_HEIGHT = 861 #460

CHAT_DISPLAY_X = 10
CHAT_DISPLAY_Y = 10
CHAT_DISPLAY_WIDTH = WINDOW_WIDTH-20
CHAT_DISPLAY_HEIGHT = WINDOW_HEIGHT-60

INPUT_X = 10
INPUT_Y = WINDOW_HEIGHT-40
INPUT_WIDTH = WINDOW_WIDTH-100
INPUT_HEIGHT = 25

BUTTON_X = WINDOW_WIDTH-80
BUTTON_Y = WINDOW_HEIGHT-40
BUTTON_WIDTH = 70
BUTTON_HEIGHT = 25

class ChatMemoryBot:
    def __init__(self, system_prompt: str, model: str = "gpt-4", max_tokens: int = 500):
        self.client = OpenAI()
        self.model = model
        self.max_tokens = max_tokens
        self.encoder = tiktoken.encoding_for_model(model)
        self.chat_history: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        print(self.chat_history)

    def _count_tokens(self, messages: List[Dict[str, str]]) -> int:
        return sum(len(self.encoder.encode(msg['content'])) for msg in messages)
        
    def _summarize_history(self, old_messages: List[Dict[str, str]]) -> str:
        summary_prompt: List[ChatCompletionMessageParam] = [
            {"role": "system", "content": "Summarize the following chat history in around 400 words"}
        ] + old_messages  # type: ignore
        print(f"\nOLD HISTORY: {old_messages}\n")

        response = self.client.chat.completions.create(
            model=self.model,
            messages=summary_prompt,
            temperature=0.3
        )
        return response.choices[0].message.content or ""

    def _trim_history_if_needed(self):
        token_count = self._count_tokens(self.chat_history)
        print(f"\nTOKEN COUNT ={token_count}")
        if token_count > self.max_tokens:
            system_msg = self.chat_history[0]
            old_messages = self.chat_history[1:-10]
            recent_messages = self.chat_history[-10:]
            summary = self._summarize_history(old_messages)
            print(f"\nTRIMMING HISTORY: {len(old_messages)} messages summarized to 1 message")
            print(f"\nSUMMARY: {summary}\n")
            self.chat_history = [
                system_msg,
                {"role": "assistant", "content": f"Summary of earlier conversation: {summary}"}
            ] + recent_messages

    def ask(self, user_input: str) -> str:
        print("\nASKING AI")
        self.chat_history.append({"role": "user", "content": user_input})
        self._trim_history_if_needed()

        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.chat_history, # type: ignore
            temperature=0.5
        )
        reply = response.choices[0].message.content or ""
#        print(f"BOT: {reply}")
        self.chat_history.append({"role": "assistant", "content": reply})
        print("\n".join(f"{idx:02d}: {msg}" for idx, msg in enumerate(self.chat_history, 1)))
        return reply

class ChatbotApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title("OpenAI API gpt-4o based Chatbot")
        str_system_prompt = (
            "You are speaking to TechBot, an expert AI assistant specializing in programming, "
            "software engineering, mathematics, physics and technology. Provide clear, concise "
             "and accurate technical answers. If code is requested, use best practices and explain "
             "your reasoning when appropriate. If you are asked for a numerical calculation then "
             "just provide the number without any explanation. "
        )

        self.bot = ChatMemoryBot(system_prompt=str_system_prompt)

        self.chat_display = ScrolledText(master, wrap=tk.WORD, state='disabled')
        self.chat_display.place(x=CHAT_DISPLAY_X, y=CHAT_DISPLAY_Y, width=CHAT_DISPLAY_WIDTH, height=CHAT_DISPLAY_HEIGHT)

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
        reply = self.bot.ask(user_text)
        self.display_message("Bot", reply)

    def display_message(self, sender: str, message: str) -> None:
        self.chat_display.configure(state='normal')
        self.chat_display.insert(tk.END, f"{sender}: {message}\n\n")
        self.chat_display.configure(state='disabled')
        self.chat_display.see(tk.END)

if __name__ == "__main__":
    root = tk.Tk()
    root.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+0+0") # Position at top-left corner
    root.resizable(False, False)  # Prevent window resizing
    ChatbotApp(root)
    root.mainloop()
