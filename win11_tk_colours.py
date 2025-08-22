# win11_tk_colours.py
import sys, os, tkinter as tk

# Optional: add a path to an X11 rgb.txt file if you have one
CANDIDATE_RGB_TXT = []
# Example: CANDIDATE_RGB_TXT = [r"C:\some\path\rgb.txt"]

WINDOWS_SYSTEM_COLOURS = {
    # Core system colours commonly recognised by Tk on Windows
    "SystemActiveBorder","SystemActiveCaption","SystemAppWorkspace",
    "SystemBackground","SystemButtonFace","SystemButtonHighlight",
    "SystemButtonShadow","SystemButtonText","SystemCaptionText",
    "SystemGrayText","SystemHighlight","SystemHighlightText",
    "SystemInactiveBorder","SystemInactiveCaption","SystemInactiveCaptionText",
    "SystemInfoBackground","SystemInfoText","SystemMenu","SystemMenuText",
    "SystemScrollbar","SystemWindow","SystemWindowFrame","SystemWindowText",
    "System3dDarkShadow","System3dLight","SystemHotLight",
    # Often present on newer Windows themes; Tk may or may not expose them – we’ll validate
    "SystemMenuHilight","SystemMenuBar",
}

CSS_SVG_COLOURS = {
    # Standard CSS/SVG colour names (case-insensitive in Tk). Helpful seed set on Windows.
    "aliceblue","antiquewhite","aqua","aquamarine","azure","beige","bisque","black",
    "blanchedalmond","blue","blueviolet","brown","burlywood","cadetblue","chartreuse",
    "chocolate","coral","cornflowerblue","cornsilk","crimson","cyan","darkblue",
    "darkcyan","darkgoldenrod","darkgray","darkgreen","darkgrey","darkkhaki",
    "darkmagenta","darkolivegreen","darkorange","darkorchid","darkred","darksalmon",
    "darkseagreen","darkslateblue","darkslategray","darkslategrey","darkturquoise",
    "darkviolet","deeppink","deepskyblue","dimgray","dimgrey","dodgerblue",
    "firebrick","floralwhite","forestgreen","fuchsia","gainsboro","ghostwhite",
    "gold","goldenrod","gray","green","greenyellow","grey","honeydew","hotpink",
    "indianred","indigo","ivory","khaki","lavender","lavenderblush","lawngreen",
    "lemonchiffon","lightblue","lightcoral","lightcyan","lightgoldenrodyellow",
    "lightgray","lightgreen","lightgrey","lightpink","lightsalmon","lightseagreen",
    "lightskyblue","lightslategray","lightslategrey","lightsteelblue","lightyellow",
    "lime","limegreen","linen","magenta","maroon","mediumaquamarine","mediumblue",
    "mediumorchid","mediumpurple","mediumseagreen","mediumslateblue",
    "mediumspringgreen","mediumturquoise","mediumvioletred","midnightblue",
    "mintcream","mistyrose","moccasin","navajowhite","navy","oldlace","olive",
    "olivedrab","orange","orangered","orchid","palegoldenrod","palegreen",
    "paleturquoise","palevioletred","papayawhip","peachpuff","peru","pink","plum",
    "powderblue","purple","red","rosybrown","royalblue","saddlebrown","salmon",
    "sandybrown","seagreen","seashell","sienna","silver","skyblue","slateblue",
    "slategray","slategrey","snow","springgreen","steelblue","tan","teal","thistle",
    "tomato","turquoise","violet","wheat","white","whitesmoke","yellow","yellowgreen",
    # A few X11-style TK specials that commonly exist on Windows builds:
    "aliceblue","antiquewhite1","antiquewhite2","antiquewhite3","antiquewhite4",
    "azure1","azure2","azure3","azure4","blue1","blue2","blue3","blue4",
    "gray0","gray100","grey0","grey100","LightGoldenrodYellow","DeepSkyBlue2",
}

def gray_names():
    out = set()
    for i in range(0, 101):
        out.add(f"gray{i}")
        out.add(f"grey{i}")
    return out

def load_x11_names_from_file():
    names = set()
    for p in CANDIDATE_RGB_TXT:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("!"):
                            continue
                        parts = line.split()
                        if len(parts) >= 4:
                            name = " ".join(parts[3:])
                            names.add(name)
            except OSError:
                pass
    return names

def is_valid_tk_colour(root, name: str) -> bool:
    try:
        root.winfo_rgb(name)
        return True
    except tk.TclError:
        return False

def main():
    # Windows console: ensure UTF-8 so weird names print nicely
    try:
        import ctypes
        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
    except Exception:
        pass

    root = tk.Tk(); root.withdraw()

    candidates = set()
    candidates |= WINDOWS_SYSTEM_COLOURS
    candidates |= CSS_SVG_COLOURS
    candidates |= gray_names()
    candidates |= load_x11_names_from_file()

    # Validate via Tk (source of truth)
    valid = sorted({n for n in candidates if is_valid_tk_colour(root, n)} , key=lambda s: s.lower())

    # Output
    for name in valid:
        print(name)
    print(f"\nTotal valid colour names: {len(valid)}", file=sys.stderr)

    # Optional: write to a file next to the script
    try:
        out_path = os.path.join(os.path.dirname(__file__), "win11_tk_colour_names.txt")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(valid))
        print(f"Wrote: {out_path}", file=sys.stderr)
    except Exception as e:
        print(f"Note: couldn’t write file: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
