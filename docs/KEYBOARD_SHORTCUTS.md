# Keyboard Shortcuts & Accessibility

A quick reference for efficient, mouse-light use of the app.

---

## Global

| Shortcut | Action |
|---|---|
| **Ctrl+S** | Save *System Prompt* (to `system_prompts/<name>.txt`) |
| **Ctrl+N** | Clear the *System Prompt* editor (does not affect chat history) |
| **Enter** (on focused button) | Activate that button (e.g., **NEW CHAT**, **DELETE**) |
| **Space** (on focused button) | Activate that button |
| **Tab / Shift+Tab** | Move focus through inputs, buttons, and comboboxes |

---

## Chat Pad

| Shortcut | Action |
|---|---|
| **Enter** in the chat input | Send message |
| **Alt+S** *(optional; if you bind it)* | Show sources (appends URL list to transcript) |

> The **Show sources** button appends links detected in the last assistant reply.

---

## Comboboxes (Model, Prompt files, Chat files)

- **Enter** loads the current selection.
- **Up/Down** arrow keys navigate items.
- **Esc** cancels dropdowns.

---

## Accessibility Notes

- Buttons are given focus (`takefocus=True`), so keyboard users can **Tab** to each control and press **Enter/Space**.
- Font sizes and UI geometry are set in code; you can raise widget sizes if needed.
