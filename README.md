# ChatBot.py — OpenAI Responses API GUI Client

## Getting Started

### Requirements
- Python 3.10+
- OpenAI API key
- Packages: `openai`, `tiktoken`
- Tkinter (bundled on Windows/macOS; install separately on some Linux distros)

### Installation
```bash
python -m venv .venv
# Windows
.venv\\Scripts\\activate
# macOS/Linux
source .venv/bin/activate
pip install --upgrade openai tiktoken
```

### Environment variables
```bash
# Windows (PowerShell)
setx OPENAI_API_KEY "sk-your-key"
$env:OPENAI_API_KEY = "sk-your-key"
# macOS/Linux
export OPENAI_API_KEY="sk-your-key"
```

### Running
```bash
python ChatBot.py
```

### Workflow
1. Author or load a system prompt from `system_prompts/`.
2. Start a new chat and converse with the selected model.
3. Save chats or prompts to reuse later.

## Codebase Overview

### Layout
- `ChatBot.py` — main Tkinter application
- `system_prompts/` — stored prompts and chat sessions
- Additional helper scripts for model discovery and audio/image demos

### ChatMemoryBot
Manages OpenAI interactions, tracks `chat_history`, counts tokens, and trims conversations when needed.

### ChatbotApp
Handles all Tkinter UI elements, file persistence, autosave, and threading for background API calls.

### Supporting Scripts
- `OpenAI_models.py`, `OpenAIbot.py`, `OpenAIbot2.py`, `OpenAIbot3.py`, `OpenAIbot_small1.py`
- `gpt-image-1.py`, `SimpleTextPad.py`, `Script_lists_all_available_OpenAI_models.py`, `tts-1.py`

## Data & Storage Locations
- `system_prompts/*.txt` — system prompt files
- `system_prompts/*.chat.json` — saved chat sessions
- `_autosave.chat.json` — last unnamed chat
- Hidden state file next to `ChatBot.py` remembers last used prompt and chat

## License
```text
MIT License © 2025 Your Name
```
