"""
Dialogs
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from ui.palettes import PALETTE, COVER_PRESETS, STATUS_OPTIONS
from ui.widgets import RoundedButton


class BookDialog(tk.Toplevel):
    ## Add / Edit book dialog
    def __init__(self, parent, db, book_id=None, default_shelf_id=None, on_save=None):
        super().__init__(parent)
        self.db = db
        self.book_id = book_id
        self.default_shelf_id = default_shelf_id
        self.on_save = on_save
        self.result = None
        self.cover_color = PALETTE["accent2"]

        self.title("Edit Book" if book_id else "Add Book")
        self.configure(bg=PALETTE["bg"])
        self.resizable(False, False)
        self.grab_set()
        self._build()

        if book_id:
            self._load(book_id)

        self.geometry("+%d+%d" % (parent.winfo_rootx()+80, parent.winfo_rooty()+60))

    def _build(self):
        pad = dict(padx=16, pady=6)
        f = tk.Frame(self, bg=PALETTE["bg"], padx=20, pady=20)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="Book Details", fg=PALETTE["accent"],
                 bg=PALETTE["bg"], font=("Georgia", 14, "bold")).grid(
                     row=0, column=0, columnspan=2, sticky="w", pady=(0,12))

        fields = [("Title *", "title"), ("Author", "author"),
                  ("Genre", "genre"), ("Year", "year")]
        self.vars = {}
        for i, (label, key) in enumerate(fields, 1):
            tk.Label(f, text=label, fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                     font=("Courier", 9)).grid(row=i, column=0, sticky="w", **pad)
            var = tk.StringVar()
            self.vars[key] = var
            e = tk.Entry(f, textvariable=var, bg=PALETTE["entry_bg"],
                         fg=PALETTE["text"], insertbackground=PALETTE["text"],
                         relief="flat", font=("Georgia", 10), width=28)
            e.grid(row=i, column=1, sticky="ew", **pad)

        # status
        tk.Label(f, text="Status", fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Courier", 9)).grid(row=5, column=0, sticky="w", **pad)
        self.status_var = tk.StringVar(value="unread")
        status_cb = ttk.Combobox(f, textvariable=self.status_var,
                                  values=STATUS_OPTIONS, state="readonly",
                                  font=("Georgia", 10), width=26)
        status_cb.grid(row=5, column=1, sticky="ew", **pad)
        self._style_combo(status_cb)

        # rating
        tk.Label(f, text="Rating", fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Courier", 9)).grid(row=6, column=0, sticky="w", **pad)
        self.rating_var = tk.IntVar(value=0)
        rating_frame = tk.Frame(f, bg=PALETTE["bg"])
        rating_frame.grid(row=6, column=1, sticky="w", padx=16, pady=6)
        self.star_btns = []
        for i in range(1, 6):
            b = tk.Label(rating_frame, text="☆", fg=PALETTE["warn"],
                         bg=PALETTE["bg"], font=("Arial", 16), cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, v=i: self._set_rating(v))
            self.star_btns.append(b)

        # cover color
        tk.Label(f, text="Cover Color", fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Courier", 9)).grid(row=7, column=0, sticky="w", **pad)
        color_frame = tk.Frame(f, bg=PALETTE["bg"])
        color_frame.grid(row=7, column=1, sticky="w", padx=16, pady=6)
        for c in COVER_PRESETS:
            swatch = tk.Label(color_frame, bg=c, width=2, height=1, cursor="hand2",
                              relief="flat")
            swatch.pack(side="left", padx=2)
            swatch.bind("<Button-1>", lambda e, col=c: self._set_cover(col))
        self.cover_preview = tk.Label(color_frame, text=" ▐", fg=self.cover_color,
                                       bg=PALETTE["bg"], font=("Arial", 18))
        self.cover_preview.pack(side="left", padx=4)

        # notes
        tk.Label(f, text="Notes", fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Courier", 9)).grid(row=8, column=0, sticky="nw", **pad)
        self.notes_text = tk.Text(f, bg=PALETTE["entry_bg"], fg=PALETTE["text"],
                                   insertbackground=PALETTE["text"], relief="flat",
                                   font=("Georgia", 10), width=28, height=4)
        self.notes_text.grid(row=8, column=1, sticky="ew", **pad)

        # shelves
        shelves = self.db.get_shelves()
        if shelves:
            tk.Label(f, text="Shelves", fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                     font=("Courier", 9)).grid(row=9, column=0, sticky="nw", **pad)
            shelf_frame = tk.Frame(f, bg=PALETTE["bg"])
            shelf_frame.grid(row=9, column=1, sticky="ew", padx=16, pady=6)
            self.shelf_vars = {}
            for shelf in shelves:
                var = tk.BooleanVar(value=(shelf["id"] == self.default_shelf_id))
                cb = tk.Checkbutton(shelf_frame, text=shelf["name"], variable=var,
                                     fg=PALETTE["text"], bg=PALETTE["bg"],
                                     selectcolor=PALETTE["entry_bg"],
                                     activebackground=PALETTE["bg"],
                                     activeforeground=PALETTE["text"],
                                     font=("Georgia", 9))
                cb.pack(anchor="w")
                self.shelf_vars[shelf["id"]] = var
        else:
            self.shelf_vars = {}

        # buttons
        btn_row = tk.Frame(f, bg=PALETTE["bg"])
        btn_row.grid(row=10, column=0, columnspan=2, pady=(16,0))
        RoundedButton(btn_row, "Save", command=self._save, width=100, height=32).pack(side="left", padx=6)
        RoundedButton(btn_row, "Cancel", command=self.destroy,
                      width=100, height=32, bg=PALETTE["text_dim"]).pack(side="left", padx=6)

    def _style_combo(self, cb):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox", fieldbackground=PALETTE["entry_bg"],
                        background=PALETTE["entry_bg"], foreground=PALETTE["text"],
                        selectbackground=PALETTE["card"], selectforeground=PALETTE["text"])

    def _set_rating(self, val):
        self.rating_var.set(val)
        for i, b in enumerate(self.star_btns):
            b.config(text="★" if i < val else "☆")

    def _set_cover(self, color):
        self.cover_color = color
        self.cover_preview.config(fg=color)

    def _load(self, book_id):
        b = self.db.get_book(book_id)
        if not b:
            return
        self.vars["title"].set(b["title"])
        self.vars["author"].set(b["author"] or "")
        self.vars["genre"].set(b["genre"] or "")
        self.vars["year"].set(str(b["year"]) if b["year"] else "")
        self.status_var.set(b["status"])
        if b["rating"]:
            self._set_rating(b["rating"])
        if b["cover_color"]:
            self._set_cover(b["cover_color"])
        self.notes_text.insert("1.0", b["notes"] or "")
        # mark current shelves
        current_shelves = {s["id"] for s in self.db.get_book_shelves(book_id)}
        for sid, var in self.shelf_vars.items():
            var.set(sid in current_shelves)

    def _save(self):
        title = self.vars["title"].get().strip()
        if not title:
            messagebox.showwarning("Required", "Title is required.", parent=self)
            return
        author = self.vars["author"].get().strip() or None
        genre  = self.vars["genre"].get().strip() or None
        year_s = self.vars["year"].get().strip()
        year   = int(year_s) if year_s.isdigit() else None
        rating = self.rating_var.get() or None
        status = self.status_var.get()
        notes  = self.notes_text.get("1.0", "end-1c").strip() or None

        if self.book_id:
            self.db.update_book(self.book_id, title, author, genre, year,
                                rating, status, notes, self.cover_color)
            bid = self.book_id
            # update shelves
            current = {s["id"] for s in self.db.get_book_shelves(bid)}
            for sid, var in self.shelf_vars.items():
                if var.get() and sid not in current:
                    self.db.assign_book_to_shelf(bid, sid)
                elif not var.get() and sid in current:
                    self.db.remove_book_from_shelf(bid, sid)
        else:
            bid = self.db.add_book(title, author, genre, year,
                                   rating, status, notes, self.cover_color)
            for sid, var in self.shelf_vars.items():
                if var.get():
                    self.db.assign_book_to_shelf(bid, sid)

        if self.on_save:
            self.on_save()
        self.destroy()


class ShelfDialog(tk.Toplevel):
    def __init__(self, parent, db, shelf_id=None, on_save=None):
        super().__init__(parent)
        self.db = db
        self.shelf_id = shelf_id
        self.on_save = on_save
        self.chosen_color = "#4A90D9"
        self.title("Edit Shelf" if shelf_id else "New Shelf")
        self.configure(bg=PALETTE["bg"])
        self.resizable(False, False)
        self.grab_set()
        self._build()
        if shelf_id:
            row = next((s for s in db.get_shelves() if s["id"] == shelf_id), None)
            if row:
                self.name_var.set(row["name"])
                self._pick(row["color"])
        self.geometry("+%d+%d" % (parent.winfo_rootx()+100, parent.winfo_rooty()+80))

    def _build(self):
        f = tk.Frame(self, bg=PALETTE["bg"], padx=24, pady=20)
        f.pack()
        tk.Label(f, text="Shelf Name", fg=PALETTE["text_dim"],
                 bg=PALETTE["bg"], font=("Courier", 9)).pack(anchor="w")
        self.name_var = tk.StringVar()
        tk.Entry(f, textvariable=self.name_var, bg=PALETTE["entry_bg"],
                 fg=PALETTE["text"], insertbackground=PALETTE["text"],
                 relief="flat", font=("Georgia", 11), width=24).pack(pady=(4,12))

        tk.Label(f, text="Color", fg=PALETTE["text_dim"],
                 bg=PALETTE["bg"], font=("Courier", 9)).pack(anchor="w")
        cf = tk.Frame(f, bg=PALETTE["bg"])
        cf.pack(anchor="w", pady=4)
        self.swatches = {}
        for c in COVER_PRESETS:
            s = tk.Label(cf, bg=c, width=2, height=1, cursor="hand2", relief="flat")
            s.pack(side="left", padx=2)
            s.bind("<Button-1>", lambda e, col=c: self._pick(col))
            self.swatches[c] = s
        self.preview = tk.Label(f, text=" ▐  Color Preview", fg=self.chosen_color,
                                 bg=PALETTE["bg"], font=("Arial", 14))
        self.preview.pack(anchor="w", pady=6)

        btn = tk.Frame(f, bg=PALETTE["bg"])
        btn.pack(pady=(10,0))
        RoundedButton(btn, "Save", command=self._save, width=90, height=30).pack(side="left", padx=4)
        RoundedButton(btn, "Cancel", command=self.destroy,
                      width=90, height=30, bg=PALETTE["text_dim"]).pack(side="left", padx=4)

    def _pick(self, color):
        self.chosen_color = color
        self.preview.config(fg=color)

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Required", "Shelf name is required.", parent=self)
            return
        if self.shelf_id:
            self.db.rename_shelf(self.shelf_id, name)
            self.db.update_shelf_color(self.shelf_id, self.chosen_color)
        else:
            self.db.add_shelf(name, self.chosen_color)
        if self.on_save:
            self.on_save()
        self.destroy()


class RecommendDialog(tk.Toplevel):
    def __init__(self, parent, db, api_key):
        super().__init__(parent)
        self.db = db
        self.api_key = api_key
        self.title("AI Book Recommendations")
        self.configure(bg=PALETTE["bg"])
        self.resizable(True, True)
        self.geometry("640x580")
        self.grab_set()
        self._build()
        self.geometry("+%d+%d" % (parent.winfo_rootx()+40, parent.winfo_rooty()+30))

    def _build(self):
        f = tk.Frame(self, bg=PALETTE["bg"], padx=20, pady=16)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="✦  AI Recommendations", fg=PALETTE["accent"],
                 bg=PALETTE["bg"], font=("Georgia", 14, "bold")).pack(anchor="w", pady=(0,10))

        mode_frame = tk.Frame(f, bg=PALETTE["bg"])
        mode_frame.pack(anchor="w", pady=(0,10))
        tk.Label(mode_frame, text="Mode:", fg=PALETTE["text_dim"],
                 bg=PALETTE["bg"], font=("Courier", 9)).pack(side="left")
        self.mode = tk.StringVar(value="custom")
        for val, lbl in [("library", "Based on my library"), ("custom", "Custom request")]:
            tk.Radiobutton(mode_frame, text=lbl, variable=self.mode, value=val,
                           fg=PALETTE["text"], bg=PALETTE["bg"],
                           selectcolor=PALETTE["entry_bg"],
                           activebackground=PALETTE["bg"], font=("Georgia", 9),
                           command=self._toggle_mode).pack(side="left", padx=8)

        self.prompt_frame = tk.Frame(f, bg=PALETTE["bg"])
        self.prompt_frame.pack(fill="x", pady=(0,10))
        tk.Label(self.prompt_frame, text="What would you like to read or learn?",
                 fg=PALETTE["text_dim"], bg=PALETTE["bg"], font=("Courier", 9)).pack(anchor="w")
        self.prompt_text = tk.Text(self.prompt_frame, bg=PALETTE["entry_bg"], fg=PALETTE["text"],
                                    insertbackground=PALETTE["text"], relief="flat",
                                    font=("Georgia", 10), width=60, height=3)
        self.prompt_text.pack(fill="x", pady=(4,0))

        btn_row = tk.Frame(f, bg=PALETTE["bg"])
        btn_row.pack(anchor="w", pady=(0,10))
        RoundedButton(btn_row, "Get Recommendations", command=self._ask,
                      width=180, height=32, font_size=9).pack(side="left")
        self.spinner = tk.Label(btn_row, text="", fg=PALETTE["warn"],
                                 bg=PALETTE["bg"], font=("Arial", 12))
        self.spinner.pack(side="left", padx=8)

        tk.Label(f, text="Results", fg=PALETTE["text_dim"],
                 bg=PALETTE["bg"], font=("Courier", 9)).pack(anchor="w")
        result_frame = tk.Frame(f, bg=PALETTE["bg"])
        result_frame.pack(fill="both", expand=True)
        self.result_box = tk.Text(result_frame, bg=PALETTE["entry_bg"], fg=PALETTE["text"],
                                   relief="flat", font=("Georgia", 10), wrap="word",
                                   state="disabled", padx=10, pady=10)
        sb = ttk.Scrollbar(result_frame, command=self.result_box.yview)
        self.result_box.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.result_box.pack(side="left", fill="both", expand=True)

    def _toggle_mode(self):
        if self.mode.get() == "library":
            self.prompt_frame.pack_forget()
        else:
            self.prompt_frame.pack(fill="x", pady=(0,10),
                                   before=self.prompt_frame.master.winfo_children()[-2]
                                   if len(self.prompt_frame.master.winfo_children()) > 2 else None)

    def _ask(self):
        if not ANTHROPIC_AVAILABLE:
            self._show("⚠ The 'anthropic' package is not installed.\n"
                       "Run: pip install anthropic")
            return
        if not self.api_key:
            self._show("⚠ No API key set. Go to Settings → Set API Key.")
            return

        self.spinner.config(text="⟳ Thinking…")
        self.update()

        mode = self.mode.get()
        library_summary = self.db.get_all_books_summary()

        if mode == "library":
            prompt = (f"Here is my personal library:\n{library_summary}\n\n"
                      f"Based on these books, recommend 5 books I would likely enjoy. "
                      f"For each, give the title, author, and a 1-2 sentence reason tailored to my taste.")
        else:
            user_q = self.prompt_text.get("1.0", "end-1c").strip()
            if not user_q:
                self.spinner.config(text="")
                messagebox.showwarning("Empty", "Please enter a request.", parent=self)
                return
            prompt = (f"My current library:\n{library_summary}\n\n"
                      f"User request: {user_q}\n\n"
                      f"Recommend 5 books that match this request. "
                      f"For each, give the title, author, and a brief (2-3 sentence) reason it fits. "
                      f"Avoid recommending books already in the library above.")

        def worker():
            try:
                client = anthropic.Anthropic(api_key=self.api_key)
                msg = client.messages.create(
                    model="claude-opus-4-6",
                    max_tokens=1024,
                    messages=[{"role": "user", "content": prompt}]
                )
                result = msg.content[0].text
            except Exception as ex:
                result = f"⚠ Error: {ex}"
            self.after(0, lambda: self._show(result))
            self.after(0, lambda: self.spinner.config(text=""))

        threading.Thread(target=worker, daemon=True).start()

    def _show(self, text):
        self.result_box.config(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", text)
        self.result_box.config(state="disabled")