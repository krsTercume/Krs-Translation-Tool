"""Keyboard diagnostic: shows exactly what the program receives when you press a key.
Run:  python key_test.py   -> press the key that types the schwa letter, then screenshot the window."""
import sys
import tkinter as tk

root = tk.Tk()
root.title("Key test")
root.geometry("640x360")
info = tk.Label(root, anchor="w", justify="left", font=("Consolas", 10),
                text=f"Python {sys.version.split()[0]}   Tk {root.tk.call('info', 'patchlevel')}")
info.pack(fill="x", padx=8, pady=(8, 0))
tk.Label(root, anchor="w", text="Click the box and press the key that types the schwa letter:").pack(fill="x", padx=8)
ent = tk.Entry(root, font=("Segoe UI", 16))
ent.pack(fill="x", padx=8, pady=4)
ent.focus_set()
log = tk.Text(root, height=12, font=("Consolas", 10))
log.pack(fill="both", expand=True, padx=8, pady=8)


def on_key(ev):
    line = (f"keysym={ev.keysym!r}  char={ev.char!r}  codepoint="
            f"{[hex(ord(c)) for c in ev.char]}  keycode={ev.keycode}  state={ev.state}\n")
    log.insert("end", line)
    log.see("end")


ent.bind("<KeyPress>", on_key)
root.mainloop()
