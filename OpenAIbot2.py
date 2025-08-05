import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from openai import OpenAI
import tiktoken
from typing import List, Dict
import threading

class ChatMemoryBot:
    def __init__(self, system_prompt: str, model: str = "gpt-4o", max_tokens: int = 120000):
        self.client = OpenAI()
        self.model = model
        self.max_tokens = max_tokens
        self.encoder = tiktoken.encoding_for_model(model)
        self.chat_history: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        print(self.chat_history)

    def _count_tokens(self, messages: List[Dict[str, str]]) -> int:
        return sum(len(self.encoder.encode(msg['content'])) for msg in messages)

    def _summarize_history(self, old_messages: List[Dict[str, str]]) -> str:
        summary_prompt = [
            {"role": "system", "content": "Summarize the following chat history in 400 words or less."}
        ] + old_messages

        response = self.client.chat.completions.create(
            model=self.model,
            messages=summary_prompt,
            temperature=0.3
        )
        strSummary = response.choices[0].message.content
        return strSummary

    def _trim_history_if_needed(self):
        token_count = self._count_tokens(self.chat_history)
        if token_count > self.max_tokens:
            system_msg = self.chat_history[0]
            old_messages = self.chat_history[1:-10]
            recent_messages = self.chat_history[-10:]
            summary = self._summarize_history(old_messages)
            print("\n***** SUMMARY ****\n")
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
            messages=self.chat_history,
            temperature=0.5
        )
        reply = response.choices[0].message.content

        token_count = self._count_tokens(self.chat_history)
        print(f"\nTOKEN COUNT ={token_count}")
        print("\n".join(f"{idx:02d}: {msg}" for idx, msg in enumerate(self.chat_history, 1)))
        #print("\n".join(str(msg) for msg in self.chat_history))
        print(f"BOT: {reply}")
        
        self.chat_history.append({"role": "assistant", "content": reply})
        return reply

class ChatbotApp:
    def __init__(self, master: tk.Tk):
        self.master = master
        master.title("OpenAI API gpt-4o based Chatbot")

        self.bot = ChatMemoryBot(system_prompt="You are speaking to Dave, a friendly AI Chatbot")

        self.chat_display = ScrolledText(master, wrap=tk.WORD, state='disabled', height=25, width=80)
        self.chat_display.place(x=10, y=10, width=580, height=400)

        self.user_input = tk.Entry(master, width=70)
        self.user_input.place(x=10, y=420, width=500, height=25)
        self.user_input.bind("<Return>", self.send_message)

        self.send_button = tk.Button(master, text="Send", command=lambda: self.send_message())
        self.send_button.place(x=520, y=420, width=70, height=25)





        #self.chat_display = ScrolledText(master, wrap=tk.WORD, state='disabled', height=25, width=80)
        #self.chat_display.pack(padx=10, pady=10)

        #self.user_input = tk.Entry(master, width=70)
        #self.user_input.pack(padx=10, pady=5, side=tk.LEFT)
        #self.user_input.bind("<Return>", self.send_message)

        #self.send_button = tk.Button(master, text="Send", command=lambda: self.send_message())
        #self.send_button.pack(pady=5, side=tk.LEFT)

    def send_message(self, event: 'tk.Event' = None):
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
    root.geometry("600x460")  # Set the window size to ensure all widgets fit

#    app = ChatbotApp(root)
    ChatbotApp(root)
    root.mainloop()
