# Prompt Presets

Long-form, opinionated system prompts intended to be loaded via the **System Prompt** editor and used to start a **NEW CHAT**. Trim to taste.

---

## How to use

1. Place `.txt` files into your repo’s `system_prompts/` folder (or any folder you launch the app from).  
2. In the app, **Load** the file in the right-hand editor.  
3. Click **NEW CHAT** to start a conversation with those rules applied.

> To *combine* prompts, paste/concatenate both into a new file. Put general templates first, then domain-specific instructions.

---

## Presets

| File | Purpose |
|---|---|
| `00-Response-Template.txt` | Universal output structure (Answer first → Details → Next steps → Summary). |
| `01-Generalist-Desktop-Assistant.txt` | Decisive desktop helper; strong defaults, structured answers. |
| `02-Senior-Code-Assistant.txt` | Code diagnosis + patch + runnable example + tests; trade-off analysis. |
| `03-Python-Tkinter-Coach.txt` | Tkinter patterns (threading with `after()`, layout, progress/cancel). |
| `04-Researcher-with-Citations.txt` | Research mode with concise citations and conflict handling. |
| `05-Robotics-Embedded-AI-Architect.txt` | LLM+vision+policy integration; timing budgets; ROS2 interfaces. |
| `06-Radio-Streaming-and-Automation.txt` | Ethical stream discovery and Selenium/Playwright automation patterns. |
| `07-3D-Printing-Enclosure-Consultant.txt` | Material selection, design rules, thermal and mounting guidance. |
| `08-Socratic-Math-Physics-Tutor.txt` | One-question-at-a-time tutoring with units and worked examples. |
| `09-Decision-Advisor-Opinionated.txt` | Options with pros/cons, decision matrix, and a clear recommendation. |

---

## Tips

- **Prioritize the first screenful** of instructions; models weight early content more.  
- **Keep it lean**: remove boilerplate; retain rules that actually change outputs.  
- **Citations**: include a short style clause if you want consistent source linking in outputs.  
- **Token discipline**: very long prompts reduce budget left for conversation turns. Your app summarizes *old* turns automatically, but a lean prompt still improves responsiveness.
