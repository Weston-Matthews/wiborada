"""
Reusable widgets
"""

import tkinter as tk
from ui.palettes import PALETTE

class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=120, height=34,
                 bg=PALETTE["accent"], fg="white", radius=8, font_size=10, **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=parent["bg"] if hasattr(parent, "__getitem__") else PALETTE["bg"],
                         highlightthickness=0, **kwargs)
        self.command = command
        self.bg_color = bg
        self.hover_color = self._darken(bg)
        self.text_val = text
        self.radius = radius
        self._draw(bg, fg, text, font_size)
        self.bind("<Enter>",    lambda e: self._draw(self.hover_color, fg, text, font_size))
        self.bind("<Leave>",    lambda e: self._draw(bg, fg, text, font_size))
        self.bind("<Button-1>", lambda e: command() if command else None)

    def _draw(self, bg, fg, text, fs):
        self.delete("all")
        w, h, r = int(self["width"]), int(self["height"]), self.radius
        self.create_arc(0,   0,   2*r, 2*r, start=90,  extent=90,  fill=bg, outline=bg)
        self.create_arc(w-2*r, 0, w, 2*r, start=0,   extent=90,  fill=bg, outline=bg)
        self.create_arc(0, h-2*r, 2*r, h,  start=180, extent=90,  fill=bg, outline=bg)
        self.create_arc(w-2*r, h-2*r, w, h,start=270, extent=90,  fill=bg, outline=bg)
        self.create_rectangle(r, 0, w-r, h, fill=bg, outline=bg)
        self.create_rectangle(0, r, w, h-r, fill=bg, outline=bg)
        self.create_text(w//2, h//2, text=text, fill=fg,
                         font=("Georgia", fs, "bold"))

    @staticmethod
    def _darken(hex_color):
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2],16), int(hex_color[2:4],16), int(hex_color[4:6],16)
        r, g, b = max(0,r-30), max(0,g-30), max(0,b-30)
        return f"#{r:02x}{g:02x}{b:02x}"


class BookCard(tk.Frame):
    # A visual book card widget
    def __init__(self, parent, book, on_click, on_edit, on_delete, **kwargs):
        super().__init__(parent, bg=PALETTE["card"], cursor="hand2",
                         relief="flat", bd=0, **kwargs)
        self.book = book
        self._build(on_click, on_edit, on_delete)

    def _build(self, on_click, on_edit, on_delete):
        # spine
        spine = tk.Frame(self, bg=self.book["cover_color"] or PALETTE["accent2"], width=10)
        spine.pack(side="left", fill="y")

        body = tk.Frame(self, bg=PALETTE["card"], padx=10, pady=8)
        body.pack(side="left", fill="both", expand=True)

        title = tk.Label(body, text=self.book["title"], fg=PALETTE["text"],
                         bg=PALETTE["card"], font=("Georgia", 11, "bold"),
                         anchor="w", wraplength=200)
        title.pack(anchor="w")

        author = tk.Label(body, text=self.book["author"] or "Unknown Author",
                          fg=PALETTE["text_dim"], bg=PALETTE["card"],
                          font=("Georgia", 9, "italic"), anchor="w")
        author.pack(anchor="w")

        meta_row = tk.Frame(body, bg=PALETTE["card"])
        meta_row.pack(anchor="w", pady=(4,0))

        status_color = STATUS_COLORS.get(self.book["status"], "#888")
        tk.Label(meta_row, text=self.book["status"].upper(),
                 fg=status_color, bg=PALETTE["card"],
                 font=("Courier", 8, "bold")).pack(side="left", padx=(0,8))

        if self.book["genre"]:
            tk.Label(meta_row, text=self.book["genre"],
                     fg=PALETTE["text_dim"], bg=PALETTE["card"],
                     font=("Courier", 8)).pack(side="left", padx=(0,8))

        if self.book["rating"]:
            stars = "★" * self.book["rating"] + "☆" * (5 - self.book["rating"])
            tk.Label(meta_row, text=stars, fg=PALETTE["warn"],
                     bg=PALETTE["card"], font=("Courier", 9)).pack(side="left")

        # action buttons
        btn_row = tk.Frame(self, bg=PALETTE["card"], padx=6, pady=4)
        btn_row.pack(side="right", anchor="center")
        tk.Label(btn_row, text="✏", fg=PALETTE["text_dim"], bg=PALETTE["card"],
                 font=("Arial", 13), cursor="hand2").pack()
        btn_row.bind("<Button-1>", lambda e: on_edit(self.book["id"]))
        btn_row.winfo_children()[0].bind("<Button-1>", lambda e: on_edit(self.book["id"]))

        del_lbl = tk.Label(btn_row, text="🗑", fg=PALETTE["accent"], bg=PALETTE["card"],
                            font=("Arial", 13), cursor="hand2")
        del_lbl.pack()
        del_lbl.bind("<Button-1>", lambda e: on_delete(self.book["id"]))

        # click on body to open detail
        for w in [body, title, author]:
            w.bind("<Button-1>", lambda e: on_click(self.book["id"]))
        self.bind("<Button-1>", lambda e: on_click(self.book["id"]))

        # hover highlight
        def on_enter(e):
            self.config(bg="#1a3a6a")
            body.config(bg="#1a3a6a")
            for c in body.winfo_children(): c.config(bg="#1a3a6a")
        def on_leave(e):
            self.config(bg=PALETTE["card"])
            body.config(bg=PALETTE["card"])
            for c in body.winfo_children(): c.config(bg=PALETTE["card"])
        self.bind("<Enter>", on_enter)
        self.bind("<Leave>", on_leave)