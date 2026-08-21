"""
Wiborada - Orthodox Patron Saint of Libraries
Program which allows for the management of a personal library
Create catagories/shelves, add books to your library, and get recommendations for books based on what you want to learn about and what you already have
"""

## Planning functions

# Create and maintain an internal database
# Create book objects with information fields
#   - Add books via ISBN entry
#   - Add books manually
# Create categories/shelfs that associate with books
# Get book recommendations based on what you want to know/read, or what you already have

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
import sys
import subprocess
import threading
import urllib.request
import urllib.error
import urllib.parse
import json as _json

# ── optional anthropic import ────────────────────────────────────────────────
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

# ── optional Pillow import for cover image display ───────────────────────────
import io as _io
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

DB_PATH = os.path.join(os.path.expanduser("~"), ".personal_library.db")


# ═══════════════════════════════════════════════════════════════════════════════
# THEME SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════

THEMES = {
    # ── Dark: warm charcoal with teal/amber accents — no navy blues ───────────
    "dark": {
        "bg":         "#1C1C1E",   # macOS-style near-black
        "sidebar":    "#242426",   # barely lifted from bg
        "card":       "#2C2C2E",   # card surface — clear separation from bg
        "card_hover": "#38383A",   # hover lift
        "accent":     "#30D158",   # Apple-green primary action
        "accent2":    "#636366",   # neutral secondary
        "text":       "#F2F2F7",   # iOS off-white — crisp, not harsh
        "text_dim":   "#8E8E93",   # iOS secondary label
        "warn":       "#FFD60A",   # vivid amber for stars
        "entry_bg":   "#1C1C1E",   # same as bg — inputs recede
        "border":     "#3A3A3C",   # subtle separator
        "menu_bg":    "#2C2C2E",
        "topbar":     "#1C1C1E",   # flush with bg — unified look
        "statsbar":   "#242426",
        "success":    "#30D158",
    },
    # ── Light: warm parchment with amber/gold accents ────────────────────────
    "light": {
        "bg":         "#F5F0E8",   # warm parchment — soft, not stark white
        "sidebar":    "#EDE7D9",   # slightly deeper sand — gentle separation
        "card":       "#FAF7F2",   # cream card surface — lifted from bg
        "card_hover": "#EDE7D9",   # hover pulls to sidebar tone
        "accent":     "#C8860A",   # warm amber gold — primary actions
        "accent2":    "#A0734A",   # deeper sienna — secondary buttons
        "text":       "#2E2416",   # warm near-black — readable, not harsh
        "text_dim":   "#7A6A52",   # muted warm brown for secondary labels
        "warn":       "#C8860A",   # same gold for stars — cohesive
        "entry_bg":   "#FAF7F2",   # cream inputs match cards
        "border":     "#D9CEBC",   # warm stone separator
        "menu_bg":    "#FAF7F2",
        "topbar":     "#2E2416",   # deep warm brown — ties to text colour
        "statsbar":   "#EDE7D9",   # matches sidebar — unified lower bar
        "success":    "#5A8A3C",   # muted olive green — reads well on warm bg
    },
}

# Live palette — mutated on theme switch; all widgets read from this
PALETTE = dict(THEMES["dark"])

STATUS_COLORS = {
    "read":    "#30D158",   # green
    "reading": "#FF9F0A",   # amber
    "unread":  "#8E8E93",   # grey
    "wishlist":"#FF375F",   # pink-red
    "digital": "#0A84FF",   # blue
}

COVER_PRESETS = [
    "#007AFF","#30D158","#FF9F0A","#FF375F","#5856D6",
    "#FF6B35","#34C759","#0A84FF","#BF5AF2","#FF2D55",
]

STATUS_OPTIONS = ["unread", "reading", "read", "wishlist"]

DIGITAL_FORMATS = (".pdf", ".epub")


def open_file(path: str):
    """Open a file with the OS default application."""
    # Normalize to absolute path with OS-native separators.
    # os.startfile on Windows requires backslashes; os.path.abspath handles this.
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found:\n{path}")
    if sys.platform.startswith("darwin"):
        subprocess.Popen(["open", path])
    elif sys.platform.startswith("win"):
        os.startfile(path)
    else:
        subprocess.Popen(["xdg-open", path])


def apply_theme(theme_name: str):
    """Mutate the global PALETTE in-place so all widgets re-read it on next paint."""
    PALETTE.update(THEMES[theme_name])


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE LAYER
# ═══════════════════════════════════════════════════════════════════════════════

class Database:
    def __init__(self, path=DB_PATH):
        self.path = path
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS shelves (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT    NOT NULL UNIQUE,
                color   TEXT    DEFAULT '#4A90D9',
                created TEXT    DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS books (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                author      TEXT,
                genre       TEXT,
                year        INTEGER,
                rating      INTEGER CHECK(rating BETWEEN 1 AND 5),
                status      TEXT DEFAULT 'unread',
                notes       TEXT,
                cover_color TEXT DEFAULT '#2C3E50',
                added       TEXT DEFAULT (datetime('now')),
                file_path   TEXT,
                is_digital  INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS book_shelves (
                book_id  INTEGER REFERENCES books(id)  ON DELETE CASCADE,
                shelf_id INTEGER REFERENCES shelves(id) ON DELETE CASCADE,
                PRIMARY KEY (book_id, shelf_id)
            );
            CREATE TABLE IF NOT EXISTS tags (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                name    TEXT    NOT NULL UNIQUE,
                color   TEXT    DEFAULT '#FF9F0A',
                created TEXT    DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS book_tags (
                book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
                tag_id  INTEGER REFERENCES tags(id)  ON DELETE CASCADE,
                PRIMARY KEY (book_id, tag_id)
            );
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        # Migrate older DBs that may not have these columns yet
        for col, definition in [("file_path", "TEXT"), ("is_digital", "INTEGER DEFAULT 0"),
                                 ("isbn", "TEXT"), ("cover_image", "BLOB")]:
            try:
                self.conn.execute(f"ALTER TABLE books ADD COLUMN {col} {definition}")
            except Exception:
                pass
        self.conn.commit()

    # ── shelves ───────────────────────────────────────────────────────────────
    def get_shelves(self):
        return self.conn.execute("SELECT * FROM shelves ORDER BY name").fetchall()

    def add_shelf(self, name, color="#4A90D9"):
        self.conn.execute("INSERT INTO shelves (name, color) VALUES (?,?)", (name, color))
        self.conn.commit()

    def rename_shelf(self, shelf_id, new_name):
        self.conn.execute("UPDATE shelves SET name=? WHERE id=?", (new_name, shelf_id))
        self.conn.commit()

    def delete_shelf(self, shelf_id):
        self.conn.execute("DELETE FROM shelves WHERE id=?", (shelf_id,))
        self.conn.commit()

    def update_shelf_color(self, shelf_id, color):
        self.conn.execute("UPDATE shelves SET color=? WHERE id=?", (color, shelf_id))
        self.conn.commit()

    # ── tags / categories ─────────────────────────────────────────────────────
    def get_tags(self):
        return self.conn.execute("SELECT * FROM tags ORDER BY name").fetchall()

    def add_tag(self, name, color="#FF9F0A"):
        self.conn.execute("INSERT INTO tags (name, color) VALUES (?,?)", (name, color))
        self.conn.commit()

    def rename_tag(self, tag_id, new_name):
        self.conn.execute("UPDATE tags SET name=? WHERE id=?", (new_name, tag_id))
        self.conn.commit()

    def delete_tag(self, tag_id):
        self.conn.execute("DELETE FROM tags WHERE id=?", (tag_id,))
        self.conn.commit()

    def update_tag_color(self, tag_id, color):
        self.conn.execute("UPDATE tags SET color=? WHERE id=?", (color, tag_id))
        self.conn.commit()

    def get_book_tags(self, book_id):
        return self.conn.execute(
            "SELECT t.* FROM tags t JOIN book_tags bt ON t.id=bt.tag_id WHERE bt.book_id=?",
            (book_id,)
        ).fetchall()

    def assign_book_to_tag(self, book_id, tag_id):
        self.conn.execute(
            "INSERT OR IGNORE INTO book_tags (book_id, tag_id) VALUES (?,?)", (book_id, tag_id))
        self.conn.commit()

    def remove_book_from_tag(self, book_id, tag_id):
        self.conn.execute(
            "DELETE FROM book_tags WHERE book_id=? AND tag_id=?", (book_id, tag_id))
        self.conn.commit()

    def get_books_by_tag(self, tag_id, search=None, status=None, digital_only=False):
        q = ("SELECT b.* FROM books b JOIN book_tags bt ON b.id=bt.book_id "
             "WHERE bt.tag_id=?")
        params = [tag_id]
        if search:
            q += " AND (b.title LIKE ? OR b.author LIKE ?)"
            params += [f"%{search}%", f"%{search}%"]
        if status:
            q += " AND b.status=?"
            params.append(status)
        if digital_only:
            q += " AND b.is_digital=1"
        q += " ORDER BY b.title"
        return self.conn.execute(q, params).fetchall()

    # ── authors ───────────────────────────────────────────────────────────────
    def get_authors(self):
        rows = self.conn.execute(
            "SELECT DISTINCT author FROM books "
            "WHERE author IS NOT NULL AND author != '' ORDER BY author"
        ).fetchall()
        return [r["author"] for r in rows]

    def get_books_by_author(self, author, search=None, status=None, digital_only=False):
        q = "SELECT b.* FROM books b WHERE b.author=?"
        params = [author]
        if search:
            q += " AND (b.title LIKE ? OR b.author LIKE ?)"
            params += [f"%{search}%", f"%{search}%"]
        if status:
            q += " AND b.status=?"
            params.append(status)
        if digital_only:
            q += " AND b.is_digital=1"
        q += " ORDER BY b.title"
        return self.conn.execute(q, params).fetchall()

    # ── books ─────────────────────────────────────────────────────────────────
    def get_books(self, shelf_id=None, search=None, status=None, digital_only=False):
        q = "SELECT b.* FROM books b"
        params = []
        conditions = []

        if shelf_id:
            q += " JOIN book_shelves bs ON b.id=bs.book_id"
            conditions.append("bs.shelf_id=?")
            params.append(shelf_id)

        if search:
            conditions.append("(b.title LIKE ? OR b.author LIKE ?)")
            params += [f"%{search}%", f"%{search}%"]
        if status:
            conditions.append("b.status=?")
            params.append(status)
        if digital_only:
            conditions.append("b.is_digital=1")

        if conditions:
            q += " WHERE " + " AND ".join(conditions)
        q += " ORDER BY b.title"
        return self.conn.execute(q, params).fetchall()

    def get_book(self, book_id):
        return self.conn.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()

    def add_book(self, title, author, genre, year, rating, status, notes, cover_color,
                 file_path=None, is_digital=0, isbn=None, cover_image=None):
        cur = self.conn.execute(
            "INSERT INTO books (title,author,genre,year,rating,status,notes,cover_color,"
            "file_path,is_digital,isbn,cover_image) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (title, author, genre, year, rating, status, notes, cover_color,
             file_path, is_digital, isbn, cover_image)
        )
        self.conn.commit()
        return cur.lastrowid

    def update_book(self, book_id, title, author, genre, year, rating, status, notes, cover_color,
                    file_path=None, is_digital=None, isbn=None, cover_image=None):
        if is_digital is not None:
            self.conn.execute(
                "UPDATE books SET title=?,author=?,genre=?,year=?,rating=?,status=?,notes=?,"
                "cover_color=?,file_path=?,is_digital=?,isbn=?,cover_image=? WHERE id=?",
                (title, author, genre, year, rating, status, notes, cover_color,
                 file_path, is_digital, isbn, cover_image, book_id)
            )
        else:
            self.conn.execute(
                "UPDATE books SET title=?,author=?,genre=?,year=?,rating=?,status=?,notes=?,"
                "cover_color=?,isbn=?,cover_image=? WHERE id=?",
                (title, author, genre, year, rating, status, notes, cover_color,
                 isbn, cover_image, book_id)
            )
        self.conn.commit()

    def delete_book(self, book_id):
        self.conn.execute("DELETE FROM books WHERE id=?", (book_id,))
        self.conn.commit()

    def get_book_shelves(self, book_id):
        return self.conn.execute(
            "SELECT s.* FROM shelves s JOIN book_shelves bs ON s.id=bs.shelf_id WHERE bs.book_id=?",
            (book_id,)
        ).fetchall()

    def assign_book_to_shelf(self, book_id, shelf_id):
        self.conn.execute(
            "INSERT OR IGNORE INTO book_shelves (book_id, shelf_id) VALUES (?,?)", (book_id, shelf_id)
        )
        self.conn.commit()

    def remove_book_from_shelf(self, book_id, shelf_id):
        self.conn.execute(
            "DELETE FROM book_shelves WHERE book_id=? AND shelf_id=?", (book_id, shelf_id)
        )
        self.conn.commit()

    def get_setting(self, key, default=None):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return row["value"] if row else default

    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value))
        self.conn.commit()

    def stats(self):
        total   = self.conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        read    = self.conn.execute("SELECT COUNT(*) FROM books WHERE status='read'").fetchone()[0]
        reading = self.conn.execute("SELECT COUNT(*) FROM books WHERE status='reading'").fetchone()[0]
        unread  = self.conn.execute("SELECT COUNT(*) FROM books WHERE status='unread'").fetchone()[0]
        shelves = self.conn.execute("SELECT COUNT(*) FROM shelves").fetchone()[0]
        return {"total": total, "read": read, "reading": reading, "unread": unread, "shelves": shelves}

    def get_all_books_summary(self):
        rows = self.conn.execute(
            "SELECT title, author, genre, status, rating FROM books ORDER BY title"
        ).fetchall()
        lines = []
        for r in rows:
            rating_str = f", rated {r['rating']}/5" if r['rating'] else ""
            lines.append(f"- {r['title']} by {r['author'] or 'Unknown'}"
                         f" ({r['genre'] or 'no genre'}, {r['status']}{rating_str})")
        return "\n".join(lines) if lines else "No books in library yet."


# ═══════════════════════════════════════════════════════════════════════════════
# REUSABLE WIDGETS
# ═══════════════════════════════════════════════════════════════════════════════

class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=120, height=34,
                 bg=None, fg="white", radius=8, font_size=10, **kwargs):
        self._btn_bg = bg or PALETTE["accent"]
        canvas_bg = PALETTE["bg"]
        try:
            canvas_bg = parent["bg"]
        except Exception:
            pass
        super().__init__(parent, width=width, height=height,
                         bg=canvas_bg, highlightthickness=0, **kwargs)
        self.command  = command
        self.fg       = fg
        self.fs       = font_size
        self.text_val = text
        self.radius   = radius
        self._normal_bg = self._btn_bg
        self._hover_bg  = self._darken(self._btn_bg)
        self._draw(self._normal_bg)
        self.bind("<Enter>",    lambda e: self._draw(self._hover_bg))
        self.bind("<Leave>",    lambda e: self._draw(self._normal_bg))
        self.bind("<Button-1>", lambda e: command() if command else None)

    def _draw(self, bg):
        self.delete("all")
        w, h, r = int(self["width"]), int(self["height"]), self.radius
        for x1, y1, x2, y2, s in [
            (0, 0, 2*r, 2*r, 90), (w-2*r, 0, w, 2*r, 0),
            (0, h-2*r, 2*r, h, 180), (w-2*r, h-2*r, w, h, 270)
        ]:
            self.create_arc(x1, y1, x2, y2, start=s, extent=90, fill=bg, outline=bg)
        self.create_rectangle(r, 0, w-r, h, fill=bg, outline=bg)
        self.create_rectangle(0, r, w, h-r, fill=bg, outline=bg)
        self.create_text(w//2, h//2, text=self.text_val, fill=self.fg,
                         font=("Georgia", self.fs, "bold"))

    def repaint(self, parent_bg):
        """Re-draw with updated canvas background after theme switch."""
        self.config(bg=parent_bg)
        self._draw(self._normal_bg)

    @staticmethod
    def _darken(hex_color):
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2],16), int(hex_color[2:4],16), int(hex_color[4:6],16)
        r, g, b = max(0,r-30), max(0,g-30), max(0,b-30)
        return f"#{r:02x}{g:02x}{b:02x}"


class BookCard(tk.Frame):
    def __init__(self, parent, book, on_click, on_edit, on_delete, on_open=None, **kwargs):
        super().__init__(parent, bg=PALETTE["card"], cursor="hand2",
                         relief="flat", bd=0, **kwargs)
        self.book = book
        self._build(on_click, on_edit, on_delete, on_open)

    def _build(self, on_click, on_edit, on_delete, on_open):
        # Left: cover thumbnail if available, else colored spine
        cover_photo = make_photo_image(self.book["cover_image"], 46, 68) if self.book["cover_image"] else None
        if cover_photo:
            cover_lbl = tk.Label(self, image=cover_photo, bg=PALETTE["card"],
                                  cursor="hand2", bd=0)
            cover_lbl.image = cover_photo  # prevent GC
            cover_lbl.pack(side="left", fill="y")
            cover_lbl.bind("<Button-1>", lambda e: on_click(self.book["id"]))
        else:
            tk.Frame(self, bg=self.book["cover_color"] or PALETTE["accent2"],
                     width=10).pack(side="left", fill="y")

        body = tk.Frame(self, bg=PALETTE["card"], padx=10, pady=8)
        body.pack(side="left", fill="both", expand=True)

        # Title row with optional digital badge
        title_row = tk.Frame(body, bg=PALETTE["card"])
        title_row.pack(anchor="w", fill="x")
        title = tk.Label(title_row, text=self.book["title"], fg=PALETTE["text"],
                         bg=PALETTE["card"], font=("Georgia", 11, "bold"),
                         anchor="w", wraplength=200)
        title.pack(side="left")
        if self.book["is_digital"]:
            ext = ""
            if self.book["file_path"]:
                ext = os.path.splitext(self.book["file_path"])[1].upper().lstrip(".")
            badge_text = ext if ext else "DIGITAL"
            tk.Label(title_row, text=f" {badge_text}", fg=STATUS_COLORS["digital"],
                     bg=PALETTE["card"], font=("Courier", 7, "bold")).pack(side="left", padx=(4,0))

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

        btn_row = tk.Frame(self, bg=PALETTE["card"], padx=6, pady=4)
        btn_row.pack(side="right", anchor="center")

        # Open file button (only for digital books with a valid path)
        if self.book["is_digital"] and self.book["file_path"] and on_open:
            open_lbl = tk.Label(btn_row, text="▶", fg=STATUS_COLORS["digital"],
                                bg=PALETTE["card"], font=("Arial", 13), cursor="hand2")
            open_lbl.pack()
            open_lbl.bind("<Button-1>", lambda e: on_open(self.book["id"]))

        edit_lbl = tk.Label(btn_row, text="✏", fg=PALETTE["text_dim"], bg=PALETTE["card"],
                            font=("Arial", 13), cursor="hand2")
        edit_lbl.pack()
        edit_lbl.bind("<Button-1>", lambda e: on_edit(self.book["id"]))
        btn_row.bind("<Button-1>", lambda e: on_edit(self.book["id"]))

        del_lbl = tk.Label(btn_row, text="🗑", fg=PALETTE["accent"], bg=PALETTE["card"],
                           font=("Arial", 13), cursor="hand2")
        del_lbl.pack()
        del_lbl.bind("<Button-1>", lambda e: on_delete(self.book["id"]))

        for w in [body, title_row, title, author]:
            w.bind("<Button-1>", lambda e: on_click(self.book["id"]))
        self.bind("<Button-1>", lambda e: on_click(self.book["id"]))

        hover_col = PALETTE["card_hover"]
        card_col  = PALETTE["card"]

        def on_enter(e):
            self.config(bg=hover_col)
            body.config(bg=hover_col)
            for c in body.winfo_children():
                try: c.config(bg=hover_col)
                except Exception: pass
        def on_leave(e):
            self.config(bg=card_col)
            body.config(bg=card_col)
            for c in body.winfo_children():
                try: c.config(bg=card_col)
                except Exception: pass
        self.bind("<Enter>", on_enter)
        self.bind("<Leave>", on_leave)


# ═══════════════════════════════════════════════════════════════════════════════
# DIGITAL BOOK IMPORT
# ═══════════════════════════════════════════════════════════════════════════════

def title_from_filename(path: str) -> str:
    """Best-effort title from a filename: strip extension, replace _ and -, title-case."""
    base = os.path.splitext(os.path.basename(path))[0]
    return base.replace("_", " ").replace("-", " ").strip()


def scan_folder_for_ebooks(folder: str):
    """Recursively find all .pdf and .epub files under folder."""
    results = []
    for root, _dirs, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(DIGITAL_FORMATS):
                results.append(os.path.join(root, f))
    return sorted(results)


class DigitalImportDialog(tk.Toplevel):
    """
    Import one or more digital books (PDF/EPUB) into the library.
    Supports single-file pick or folder scan.
    """
    def __init__(self, parent, db, default_shelf_id=None, on_save=None):
        super().__init__(parent)
        self.db = db
        self.default_shelf_id = default_shelf_id
        self.on_save = on_save
        self._files = []
        self._check_vars = []
        self._title_vars = []
        self._shelf_vars = {}
        # Pre-initialise so callbacks never hit AttributeError even if somehow
        # called before _build completes (Windows event loop quirk)
        self.rows_frame = None
        self._list_canvas = None

        self.title("Import Digital Books")
        self.configure(bg=PALETTE["bg"])
        self.resizable(True, True)
        self.geometry("700x540")
        self.grab_set()
        self._build()
        self.geometry("+%d+%d" % (parent.winfo_rootx()+60, parent.winfo_rooty()+50))

    def _build(self):
        # Pack order: top → bottom → middle(expand).
        # bottom must be packed BEFORE the expanding middle so it's never pushed off screen.

        # ── TOP: header + file-picker buttons ────────────────────────────────
        top = tk.Frame(self, bg=PALETTE["bg"], padx=20, pady=14)
        top.pack(side="top", fill="x")

        tk.Label(top, text="📂  Import Digital Books", fg=PALETTE["accent"],
                 bg=PALETTE["bg"], font=("Georgia", 14, "bold")).pack(anchor="w", pady=(0,4))
        tk.Label(top, text="Add PDF or EPUB files directly to your library.",
                 fg=PALETTE["text_dim"], bg=PALETTE["bg"], font=("Courier", 8)).pack(anchor="w", pady=(0,10))

        picker_row = tk.Frame(top, bg=PALETTE["bg"])
        picker_row.pack(anchor="w")
        RoundedButton(picker_row, "📄 Add File(s)", command=self._pick_files,
                      width=130, height=30, bg=PALETTE["accent2"], font_size=9).pack(side="left", padx=(0,8))
        RoundedButton(picker_row, "📁 Scan Folder", command=self._scan_folder,
                      width=130, height=30, bg=PALETTE["card"], font_size=9).pack(side="left")

        self.file_count_lbl = tk.Label(top, text="No files selected.", fg=PALETTE["text_dim"],
                                        bg=PALETTE["bg"], font=("Courier", 8))
        self.file_count_lbl.pack(anchor="w", pady=(8,0))

        # ── BOTTOM: shelves + action buttons (packed before list so always visible) ──
        bottom = tk.Frame(self, bg=PALETTE["bg"], padx=20, pady=12)
        bottom.pack(side="bottom", fill="x")

        shelves = self.db.get_shelves()
        if shelves:
            tk.Label(bottom, text="Add to shelf:", fg=PALETTE["text_dim"],
                     bg=PALETTE["bg"], font=("Courier", 8)).pack(anchor="w")
            shelf_row = tk.Frame(bottom, bg=PALETTE["bg"])
            shelf_row.pack(anchor="w", pady=(2,8))
            for shelf in shelves:
                var = tk.BooleanVar(value=(shelf["id"] == self.default_shelf_id))
                tk.Checkbutton(shelf_row, text=shelf["name"], variable=var,
                               fg=PALETTE["text"], bg=PALETTE["bg"],
                               selectcolor=PALETTE["entry_bg"],
                               activebackground=PALETTE["bg"],
                               font=("Georgia", 9)).pack(side="left", padx=6)
                self._shelf_vars[shelf["id"]] = var

        act_row = tk.Frame(bottom, bg=PALETTE["bg"])
        act_row.pack(anchor="w")
        RoundedButton(act_row, "Import Selected", command=self._import,
                      width=140, height=32, font_size=9).pack(side="left", padx=(0,8))
        RoundedButton(act_row, "Select All", command=self._select_all,
                      width=100, height=32, bg=PALETTE["card"], font_size=9).pack(side="left", padx=(0,8))
        RoundedButton(act_row, "Cancel", command=self.destroy,
                      width=90, height=32, bg=PALETTE["text_dim"], font_size=9).pack(side="left")

        self.status_lbl = tk.Label(bottom, text="", fg=PALETTE["success"],
                                    bg=PALETTE["bg"], font=("Courier", 8))
        self.status_lbl.pack(anchor="w", pady=(6,0))

        # ── MIDDLE: scrollable file list (expands to fill remaining space) ────
        list_frame = tk.Frame(self, bg=PALETTE["bg"], padx=20)
        list_frame.pack(side="top", fill="both", expand=True)

        hdr = tk.Frame(list_frame, bg=PALETTE["card"], pady=4)
        hdr.pack(fill="x")
        tk.Label(hdr, text=" ☑", fg=PALETTE["text_dim"], bg=PALETTE["card"],
                 font=("Arial", 11), width=3).pack(side="left")
        tk.Label(hdr, text="Filename", fg=PALETTE["text_dim"], bg=PALETTE["card"],
                 font=("Courier", 8, "bold"), width=30, anchor="w").pack(side="left", padx=4)
        tk.Label(hdr, text="Title (editable)", fg=PALETTE["text_dim"], bg=PALETTE["card"],
                 font=("Courier", 8, "bold"), width=28, anchor="w").pack(side="left", padx=4)
        tk.Label(hdr, text="Fmt", fg=PALETTE["text_dim"], bg=PALETTE["card"],
                 font=("Courier", 8, "bold"), width=5).pack(side="left")

        canvas = tk.Canvas(list_frame, bg=PALETTE["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        self.rows_frame = tk.Frame(canvas, bg=PALETTE["bg"])
        self.rows_frame.bind("<Configure>",
                              lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.rows_frame, anchor="nw")
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))
        canvas.bind("<Button-4>",   lambda e: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>",   lambda e: canvas.yview_scroll(1, "units"))
        self._list_canvas = canvas

    def _pick_files(self):
        paths = filedialog.askopenfilenames(
            title="Select PDF/EPUB files",
            filetypes=[("eBooks", "*.pdf *.epub"), ("PDF", "*.pdf"), ("EPUB", "*.epub")]
        )
        if paths:
            self._add_files(list(paths))

    def _scan_folder(self):
        folder = filedialog.askdirectory(title="Select folder to scan")
        if not folder:
            return
        found = scan_folder_for_ebooks(folder)
        if not found:
            messagebox.showinfo("No files found",
                                "No PDF or EPUB files were found in that folder.", parent=self)
            return
        self._add_files(found)

    def _add_files(self, paths):
        existing = set(self._files)
        new = [p for p in paths if p not in existing]
        self._files.extend(new)
        if self.rows_frame is not None:
            self._rebuild_rows()
        count = len(self._files)
        self.file_count_lbl.config(text=f"{count} file{'s' if count != 1 else ''} staged.")

    def _rebuild_rows(self):
        if self.rows_frame is None:
            return
        for w in self.rows_frame.winfo_children():
            w.destroy()
        self._check_vars = []
        self._title_vars = []

        for path in self._files:
            var = tk.BooleanVar(value=True)
            title_var = tk.StringVar(value=title_from_filename(path))
            self._check_vars.append(var)
            self._title_vars.append(title_var)

            row = tk.Frame(self.rows_frame, bg=PALETTE["bg"])
            row.pack(fill="x", pady=1)

            # Manual checkbox label — tk.Checkbutton is unreliable inside
            # canvas-embedded frames on Windows, so we toggle via a Label instead.
            chk_lbl = tk.Label(row, text="☑", fg=PALETTE["success"],
                                bg=PALETTE["bg"], font=("Arial", 13), cursor="hand2", width=2)
            chk_lbl.pack(side="left", padx=(2, 0))

            def _toggle(e, v=var, lbl=chk_lbl):
                v.set(not v.get())
                lbl.config(text="☑" if v.get() else "☐",
                            fg=PALETTE["success"] if v.get() else PALETTE["text_dim"])

            chk_lbl.bind("<Button-1>", _toggle)

            fname = os.path.basename(path)
            if len(fname) > 32: fname = fname[:29] + "…"
            tk.Label(row, text=fname, fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                     font=("Courier", 8), width=32, anchor="w").pack(side="left", padx=4)

            tk.Entry(row, textvariable=title_var, bg=PALETTE["entry_bg"],
                     fg=PALETTE["text"], insertbackground=PALETTE["text"],
                     relief="flat", font=("Georgia", 9), width=28).pack(side="left", padx=4)

            ext = os.path.splitext(path)[1].upper().lstrip(".")
            tk.Label(row, text=ext, fg=STATUS_COLORS["digital"], bg=PALETTE["bg"],
                     font=("Courier", 8, "bold"), width=5).pack(side="left")

        self._list_canvas.configure(scrollregion=self._list_canvas.bbox("all"))

    def _select_all(self):
        for v in self._check_vars:
            v.set(True)
        # Refresh the checkbox labels to show checked state
        self._rebuild_rows_visual()

    def _rebuild_rows_visual(self):
        """Sync checkbox label glyphs to current var state without rebuilding rows."""
        for row in self.rows_frame.winfo_children():
            children = row.winfo_children()
            if not children:
                continue
            idx = list(self.rows_frame.winfo_children()).index(row)
            if idx < len(self._check_vars):
                v = self._check_vars[idx]
                lbl = children[0]  # first child is always the checkbox label
                try:
                    lbl.config(text="☑" if v.get() else "☐",
                                fg=PALETTE["success"] if v.get() else PALETTE["text_dim"])
                except Exception:
                    pass

    def _import(self):
        if not self._files:
            messagebox.showwarning("Nothing to import", "Add some files first.", parent=self)
            return

        imported = 0
        skipped  = 0
        for i, path in enumerate(self._files):
            if not self._check_vars[i].get():
                skipped += 1
                continue
            title = self._title_vars[i].get().strip() or title_from_filename(path)
            ext   = os.path.splitext(path)[1].lower()
            bid = self.db.add_book(
                title=title, author=None, genre=None, year=None,
                rating=None, status="unread", notes=None,
                cover_color="#2980B9",
                file_path=path, is_digital=1
            )
            for sid, var in self._shelf_vars.items():
                if var.get():
                    self.db.assign_book_to_shelf(bid, sid)
            imported += 1

        msg = f"Imported {imported} book{'s' if imported != 1 else ''}."
        if skipped:
            msg += f" ({skipped} skipped)"
        self.status_lbl.config(text=f"✓ {msg}")
        if self.on_save:
            self.on_save()
        self.after(1200, self.destroy)


# ═══════════════════════════════════════════════════════════════════════════════
# ISBN / OPEN LIBRARY LOOKUP
# ═══════════════════════════════════════════════════════════════════════════════

def fetch_book_by_isbn(isbn: str) -> dict:
    """
    Query the Open Library Books API for a given ISBN.
    Returns a dict with keys: title, author, genre, year, description
    Raises ValueError with a human-readable message on failure.
    """
    isbn_clean = isbn.strip().replace("-", "").replace(" ", "").upper()
    # ISBN-10 may end with 'X' as a check digit; ISBN-13 is all digits
    valid_10 = len(isbn_clean) == 10 and isbn_clean[:9].isdigit() and (isbn_clean[9].isdigit() or isbn_clean[9] == "X")
    valid_13 = len(isbn_clean) == 13 and isbn_clean.isdigit()
    if not (valid_10 or valid_13):
        raise ValueError(f'"{isbn_clean}" doesn\'t look like a valid ISBN-10 or ISBN-13.\nCheck for typos and try again.')

    url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_clean}&format=json&jscmd=data"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PersonalLibraryApp/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.URLError as e:
        raise ValueError(f"Network error: {e.reason}")

    data = _json.loads(raw)
    key = f"ISBN:{isbn_clean}"
    if key not in data:
        raise ValueError(f"No book found for ISBN {isbn_clean}.")

    book = data[key]

    title = book.get("title", "")

    authors = book.get("authors", [])
    author = ", ".join(a.get("name", "") for a in authors) if authors else ""

    # subjects → genre (take first subject as a hint)
    subjects = book.get("subjects", [])
    genre = subjects[0].get("name", "") if subjects and isinstance(subjects[0], dict) else (
        subjects[0] if subjects and isinstance(subjects[0], str) else "")

    # publish_date → year
    pub_date = book.get("publish_date", "")
    year = None
    for token in pub_date.split():
        if token.isdigit() and len(token) == 4:
            year = int(token)
            break

    # description / notes
    desc_raw = book.get("notes", "") or book.get("description", "")
    if isinstance(desc_raw, dict):
        desc_raw = desc_raw.get("value", "")
    description = str(desc_raw).strip()

    # number_of_pages
    pages = book.get("number_of_pages")

    # cover image bytes (None if unavailable)
    cover_image = _fetch_cover_bytes(isbn_clean)

    return {
        "title":        title,
        "author":       author,
        "genre":        genre,
        "year":         year,
        "description":  description,
        "pages":        pages,
        "isbn":         isbn_clean,
        "cover_image":  cover_image,
    }


def _fetch_cover_bytes(isbn_clean: str):
    """Download cover image from Open Library. Returns bytes or None."""
    url = f"https://covers.openlibrary.org/b/isbn/{isbn_clean}-M.jpg"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "PersonalLibraryApp/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = resp.read()
        # Open Library returns a tiny 1×1 placeholder when no cover exists
        if len(data) < 500:
            return None
        return data
    except Exception:
        return None


def make_photo_image(image_bytes, width: int, height: int):
    """
    Convert raw JPEG/PNG bytes to a Tk PhotoImage scaled to fit within (width × height).
    Requires Pillow. Returns None if Pillow is unavailable or on any error.
    """
    if not PIL_AVAILABLE or not image_bytes:
        return None
    try:
        img = Image.open(_io.BytesIO(image_bytes))
        img.thumbnail((width, height), Image.LANCZOS)
        return ImageTk.PhotoImage(img)
    except Exception:
        return None


class ISBNLookupDialog(tk.Toplevel):
    """
    Step-1 dialog: enter an ISBN, fetch from Open Library, preview result,
    then open BookDialog pre-filled with the data.
    """
    def __init__(self, parent, db, default_shelf_id=None, on_save=None):
        super().__init__(parent)
        self.parent_win    = parent
        self.db            = db
        self.default_shelf_id = default_shelf_id
        self.on_save       = on_save
        self.fetched_data  = None

        self.title("Add Book by ISBN")
        self.configure(bg=PALETTE["bg"])
        self.resizable(False, False)
        self.grab_set()
        self._build()
        self.geometry("+%d+%d" % (parent.winfo_rootx()+90, parent.winfo_rooty()+70))

    def _build(self):
        f = tk.Frame(self, bg=PALETTE["bg"], padx=24, pady=20)
        f.pack(fill="both", expand=True)

        # Header
        tk.Label(f, text="🔍  Look Up by ISBN", fg=PALETTE["accent"],
                 bg=PALETTE["bg"], font=("Georgia", 14, "bold")).pack(anchor="w", pady=(0,4))
        tk.Label(f, text="Enter a 10 or 13-digit ISBN to fetch book details from Open Library.",
                 fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Courier", 8), wraplength=360).pack(anchor="w", pady=(0,14))

        # ISBN entry row
        isbn_row = tk.Frame(f, bg=PALETTE["bg"])
        isbn_row.pack(fill="x", pady=(0,10))
        tk.Label(isbn_row, text="ISBN:", fg=PALETTE["text_dim"],
                 bg=PALETTE["bg"], font=("Courier", 9), width=6).pack(side="left")
        self.isbn_var = tk.StringVar()
        isbn_entry = tk.Entry(isbn_row, textvariable=self.isbn_var,
                               bg=PALETTE["entry_bg"], fg=PALETTE["text"],
                               insertbackground=PALETTE["text"],
                               relief="flat", font=("Georgia", 12), width=22)
        isbn_entry.pack(side="left", padx=(4,8), ipady=4)
        isbn_entry.focus_set()
        isbn_entry.bind("<Return>", lambda e: self._lookup())

        self.lookup_btn = RoundedButton(isbn_row, "Fetch", command=self._lookup,
                                         width=80, height=32, font_size=9)
        self.lookup_btn.pack(side="left")
        self.spinner_lbl = tk.Label(isbn_row, text="", fg=PALETTE["warn"],
                                     bg=PALETTE["bg"], font=("Arial", 12))
        self.spinner_lbl.pack(side="left", padx=6)

        # Preview card (hidden until data arrives) — cover thumb + text side by side
        self.preview_frame = tk.Frame(f, bg=PALETTE["card"],
                                       highlightbackground=PALETTE["accent2"],
                                       highlightthickness=1)
        # not packed yet

        preview_inner = tk.Frame(self.preview_frame, bg=PALETTE["card"])
        preview_inner.pack(fill="x", padx=14, pady=12)

        # Cover thumbnail slot
        self._preview_cover_lbl = tk.Label(preview_inner, bg=PALETTE["entry_bg"],
                                            width=56, height=80,
                                            relief="flat")
        self._preview_cover_lbl.pack(side="left", anchor="n", padx=(0, 12))

        preview_text = tk.Frame(preview_inner, bg=PALETTE["card"])
        preview_text.pack(side="left", fill="both", expand=True)

        self.preview_title  = tk.Label(preview_text, text="", fg=PALETTE["text"],
                                        bg=PALETTE["card"], font=("Georgia", 12, "bold"),
                                        wraplength=280, justify="left", anchor="w")
        self.preview_title.pack(anchor="w", pady=(0,2))

        self.preview_author = tk.Label(preview_text, text="", fg=PALETTE["text_dim"],
                                        bg=PALETTE["card"], font=("Georgia", 10, "italic"),
                                        anchor="w")
        self.preview_author.pack(anchor="w")

        self.preview_meta   = tk.Label(preview_text, text="", fg=PALETTE["text_dim"],
                                        bg=PALETTE["card"], font=("Courier", 8), anchor="w")
        self.preview_meta.pack(anchor="w", pady=(2,4))

        self.preview_desc   = tk.Label(preview_text, text="", fg=PALETTE["text_dim"],
                                        bg=PALETTE["card"], font=("Georgia", 9),
                                        wraplength=280, justify="left", anchor="w")
        self.preview_desc.pack(anchor="w")

        # Error label
        self.error_lbl = tk.Label(f, text="", fg=PALETTE["accent"],
                                   bg=PALETTE["bg"], font=("Courier", 9), wraplength=360)
        self.error_lbl.pack(anchor="w")

        # Bottom buttons
        btn_row = tk.Frame(f, bg=PALETTE["bg"])
        btn_row.pack(pady=(14,0))
        self.add_btn = RoundedButton(btn_row, "Add to Library →",
                                      command=self._open_book_dialog,
                                      width=150, height=32, font_size=9)
        self.add_btn.pack(side="left", padx=6)
        self.add_btn.pack_forget()   # hidden until fetch succeeds

        RoundedButton(btn_row, "Cancel", command=self.destroy,
                      width=90, height=32, bg=PALETTE["text_dim"],
                      font_size=9).pack(side="left", padx=6)

    def _lookup(self):
        isbn = self.isbn_var.get().strip()
        if not isbn:
            return
        self.error_lbl.config(text="")
        self.preview_frame.pack_forget()
        self.add_btn.pack_forget()
        self.spinner_lbl.config(text="⟳ Fetching…")
        self.update()

        def worker():
            try:
                data = fetch_book_by_isbn(isbn)
                self.after(0, lambda: self._show_preview(data))
            except ValueError as e:
                self.after(0, lambda: self._show_error(str(e)))
            finally:
                self.after(0, lambda: self.spinner_lbl.config(text=""))

        threading.Thread(target=worker, daemon=True).start()

    def _show_preview(self, data):
        self.fetched_data = data
        self.preview_title.config(text=data["title"] or "(No title)")
        self.preview_author.config(text=f"by {data['author']}" if data["author"] else "Author unknown")
        meta_parts = []
        if data["year"]:    meta_parts.append(str(data["year"]))
        if data["genre"]:   meta_parts.append(data["genre"])
        if data["pages"]:   meta_parts.append(f"{data['pages']} pages")
        if data["isbn"]:    meta_parts.append(f"ISBN {data['isbn']}")
        self.preview_meta.config(text="  ·  ".join(meta_parts))
        desc = (data["description"] or "No description available.")
        if len(desc) > 220:
            desc = desc[:220].rstrip() + "…"
        self.preview_desc.config(text=desc)

        # Cover thumbnail
        photo = make_photo_image(data.get("cover_image"), 56, 80) if data.get("cover_image") else None
        if photo:
            self._preview_cover_lbl.config(image=photo, text="", width=56, height=80)
            self._preview_cover_lbl.image = photo
        else:
            self._preview_cover_lbl.config(image="", text="No\nCover",
                                            fg=PALETTE["text_dim"],
                                            font=("Courier", 7))
            self._preview_cover_lbl.image = None

        self.preview_frame.pack(fill="x", pady=(0,8))
        self.add_btn.pack(side="left", padx=6)
        self.error_lbl.config(text="")

    def _show_error(self, msg):
        self.error_lbl.config(text=f"⚠  {msg}")
        self.fetched_data = None

    def _open_book_dialog(self):
        if not self.fetched_data:
            return
        self.destroy()
        # Open BookDialog pre-filled with fetched data
        dlg = BookDialog(self.parent_win, self.db,
                         default_shelf_id=self.default_shelf_id,
                         on_save=self.on_save,
                         prefill=self.fetched_data)


# ═══════════════════════════════════════════════════════════════════════════════
# DIALOGS
# ═══════════════════════════════════════════════════════════════════════════════

class BookDialog(tk.Toplevel):
    def __init__(self, parent, db, book_id=None, default_shelf_id=None, on_save=None, prefill=None):
        super().__init__(parent)
        self.db = db
        self.book_id = book_id
        self.default_shelf_id = default_shelf_id
        self.on_save = on_save
        self.cover_color = PALETTE["accent2"]
        self._loaded_file_path   = None
        self._loaded_is_digital  = 0
        self._loaded_cover_image = None

        self.title("Edit Book" if book_id else "Add Book")
        self.configure(bg=PALETTE["bg"])
        self.resizable(False, False)
        self.grab_set()
        self._build()
        if book_id:
            self._load(book_id)
        elif prefill:
            self._apply_prefill(prefill)
        self.geometry("+%d+%d" % (parent.winfo_rootx()+80, parent.winfo_rooty()+60))

    def _build(self):
        pad = dict(padx=16, pady=6)
        f = tk.Frame(self, bg=PALETTE["bg"], padx=20, pady=20)
        f.pack(fill="both", expand=True)

        tk.Label(f, text="Book Details", fg=PALETTE["accent"],
                 bg=PALETTE["bg"], font=("Georgia", 14, "bold")).grid(
                     row=0, column=0, columnspan=2, sticky="w", pady=(0,12))

        # Cover image preview — right column, spans rows 1-5
        cover_outer = tk.Frame(f, bg=PALETTE["border"], padx=1, pady=1)
        cover_outer.grid(row=1, column=2, rowspan=5, padx=(16, 0), pady=4, sticky="n")
        self._cover_frame = tk.Frame(cover_outer, bg=PALETTE["entry_bg"], width=80, height=112)
        self._cover_frame.pack()
        self._cover_frame.pack_propagate(False)
        self._cover_lbl = tk.Label(self._cover_frame, bg=PALETTE["entry_bg"],
                                    text="No\nCover", fg=PALETTE["text_dim"],
                                    font=("Courier", 7), justify="center")
        self._cover_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # Rows 1-4: Title, Author, Genre, Year
        fields = [("Title *", "title"), ("Author", "author"),
                  ("Genre", "genre"), ("Year", "year")]
        self.vars = {}
        for i, (label, key) in enumerate(fields, 1):
            tk.Label(f, text=label, fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                     font=("Courier", 9)).grid(row=i, column=0, sticky="w", **pad)
            var = tk.StringVar()
            self.vars[key] = var
            tk.Entry(f, textvariable=var, bg=PALETTE["entry_bg"],
                     fg=PALETTE["text"], insertbackground=PALETTE["text"],
                     relief="flat", font=("Georgia", 10), width=28
                     ).grid(row=i, column=1, sticky="ew", **pad)

        # Row 5: ISBN (saved field) + inline Fetch button
        tk.Label(f, text="ISBN", fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Courier", 9)).grid(row=5, column=0, sticky="w", **pad)
        isbn_frame = tk.Frame(f, bg=PALETTE["bg"])
        isbn_frame.grid(row=5, column=1, sticky="ew", padx=16, pady=6)
        self._isbn_var = tk.StringVar()
        isbn_entry = tk.Entry(isbn_frame, textvariable=self._isbn_var,
                               bg=PALETTE["entry_bg"], fg=PALETTE["text"],
                               insertbackground=PALETTE["text"],
                               relief="flat", font=("Georgia", 10), width=18)
        isbn_entry.pack(side="left", ipady=3)
        isbn_entry.bind("<Return>", lambda e: self._isbn_fetch())
        RoundedButton(isbn_frame, "Fetch", command=self._isbn_fetch,
                      width=62, height=26, font_size=8).pack(side="left", padx=(8, 4))
        self._isbn_spinner = tk.Label(isbn_frame, text="", fg=PALETTE["warn"],
                                       bg=PALETTE["bg"], font=("Arial", 10))
        self._isbn_spinner.pack(side="left")

        # Row 6: Status
        tk.Label(f, text="Status", fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Courier", 9)).grid(row=6, column=0, sticky="w", **pad)
        self.status_var = tk.StringVar(value="unread")
        status_cb = ttk.Combobox(f, textvariable=self.status_var,
                                  values=STATUS_OPTIONS, state="readonly",
                                  font=("Georgia", 10), width=26)
        status_cb.grid(row=6, column=1, sticky="ew", **pad)
        self._style_combo()

        # Row 7: Rating
        tk.Label(f, text="Rating", fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Courier", 9)).grid(row=7, column=0, sticky="w", **pad)
        self.rating_var = tk.IntVar(value=0)
        rating_frame = tk.Frame(f, bg=PALETTE["bg"])
        rating_frame.grid(row=7, column=1, sticky="w", padx=16, pady=6)
        self.star_btns = []
        for i in range(1, 6):
            b = tk.Label(rating_frame, text="☆", fg=PALETTE["warn"],
                         bg=PALETTE["bg"], font=("Arial", 16), cursor="hand2")
            b.pack(side="left")
            b.bind("<Button-1>", lambda e, v=i: self._set_rating(v))
            self.star_btns.append(b)

        # Row 8: Cover Color
        tk.Label(f, text="Cover Color", fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Courier", 9)).grid(row=8, column=0, sticky="w", **pad)
        color_frame = tk.Frame(f, bg=PALETTE["bg"])
        color_frame.grid(row=8, column=1, sticky="w", padx=16, pady=6)
        for c in COVER_PRESETS:
            swatch = tk.Label(color_frame, bg=c, width=2, height=1,
                              cursor="hand2", relief="flat")
            swatch.pack(side="left", padx=2)
            swatch.bind("<Button-1>", lambda e, col=c: self._set_cover(col))
        self.cover_preview = tk.Label(color_frame, text=" ▐", fg=self.cover_color,
                                       bg=PALETTE["bg"], font=("Arial", 18))
        self.cover_preview.pack(side="left", padx=4)

        # Row 9: Notes
        tk.Label(f, text="Notes", fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Courier", 9)).grid(row=9, column=0, sticky="nw", **pad)
        self.notes_text = tk.Text(f, bg=PALETTE["entry_bg"], fg=PALETTE["text"],
                                   insertbackground=PALETTE["text"], relief="flat",
                                   font=("Georgia", 10), width=28, height=4)
        self.notes_text.grid(row=9, column=1, sticky="ew", **pad)

        # Row 10: File path (shown only when editing a digital book, gridded lazily in _load)
        self._file_path_lbl = tk.Label(f, text="", fg=STATUS_COLORS["digital"],
                                        bg=PALETTE["bg"], font=("Courier", 8),
                                        wraplength=260, anchor="w", justify="left")
        self._file_path_row_label = tk.Label(f, text="File", fg=PALETTE["text_dim"],
                                              bg=PALETTE["bg"], font=("Courier", 9))

        # Row 11: Shelves
        shelves = self.db.get_shelves()
        if shelves:
            tk.Label(f, text="Shelves", fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                     font=("Courier", 9)).grid(row=11, column=0, sticky="nw", **pad)

            SHELF_ITEM_H = 22  # px per checkbutton row
            MAX_VISIBLE  = 5
            show_scroll  = len(shelves) > MAX_VISIBLE

            if show_scroll:
                # Scrollable canvas container
                canvas_h = MAX_VISIBLE * SHELF_ITEM_H + 4
                shelf_canvas = tk.Canvas(f, bg=PALETTE["entry_bg"],
                                          highlightbackground=PALETTE["border"],
                                          highlightthickness=1,
                                          height=canvas_h, width=180)
                shelf_canvas.grid(row=11, column=1, sticky="w", padx=16, pady=6)
                shelf_sb = ttk.Scrollbar(f, orient="vertical",
                                          command=shelf_canvas.yview)
                shelf_sb.grid(row=11, column=1, sticky="nse", padx=(0, 16), pady=6)
                shelf_canvas.configure(yscrollcommand=shelf_sb.set)

                shelf_frame = tk.Frame(shelf_canvas, bg=PALETTE["entry_bg"])
                shelf_canvas.create_window((0, 0), window=shelf_frame, anchor="nw")
                shelf_frame.bind("<Configure>",
                    lambda e: shelf_canvas.configure(
                        scrollregion=shelf_canvas.bbox("all")))

                # Forward scroll wheel events
                def _shelf_scroll(e):
                    shelf_canvas.yview_scroll(-1 * (e.delta // 120), "units")
                shelf_canvas.bind("<MouseWheel>", _shelf_scroll)
                shelf_frame.bind("<MouseWheel>", _shelf_scroll)
            else:
                shelf_frame = tk.Frame(f, bg=PALETTE["bg"])
                shelf_frame.grid(row=11, column=1, sticky="ew", padx=16, pady=6)

            bg = PALETTE["entry_bg"] if show_scroll else PALETTE["bg"]
            self.shelf_vars = {}
            for shelf in shelves:
                var = tk.BooleanVar(value=(shelf["id"] == self.default_shelf_id))
                tk.Checkbutton(shelf_frame, text=shelf["name"], variable=var,
                               fg=PALETTE["text"], bg=bg,
                               selectcolor=PALETTE["entry_bg"],
                               activebackground=bg,
                               activeforeground=PALETTE["text"],
                               font=("Georgia", 9)).pack(anchor="w", padx=4)
                self.shelf_vars[shelf["id"]] = var
        else:
            self.shelf_vars = {}

        # Row 12: Categories / Tags
        tags = self.db.get_tags()
        if tags:
            tk.Label(f, text="Categories", fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                     font=("Courier", 9)).grid(row=12, column=0, sticky="nw", **pad)
            TAG_ITEM_H   = 22
            MAX_TAG_VIS  = 5
            show_tag_scroll = len(tags) > MAX_TAG_VIS
            if show_tag_scroll:
                tag_canvas_h = MAX_TAG_VIS * TAG_ITEM_H + 4
                tag_canvas = tk.Canvas(f, bg=PALETTE["entry_bg"],
                                       highlightbackground=PALETTE["border"],
                                       highlightthickness=1,
                                       height=tag_canvas_h, width=180)
                tag_canvas.grid(row=12, column=1, sticky="w", padx=16, pady=6)
                tag_sb = ttk.Scrollbar(f, orient="vertical", command=tag_canvas.yview)
                tag_sb.grid(row=12, column=1, sticky="nse", padx=(0, 16), pady=6)
                tag_canvas.configure(yscrollcommand=tag_sb.set)
                tag_frame = tk.Frame(tag_canvas, bg=PALETTE["entry_bg"])
                tag_canvas.create_window((0, 0), window=tag_frame, anchor="nw")
                tag_frame.bind("<Configure>",
                    lambda e: tag_canvas.configure(scrollregion=tag_canvas.bbox("all")))
                def _tag_scroll(e):
                    tag_canvas.yview_scroll(-1 * (e.delta // 120), "units")
                tag_canvas.bind("<MouseWheel>", _tag_scroll)
                tag_frame.bind("<MouseWheel>", _tag_scroll)
            else:
                tag_frame = tk.Frame(f, bg=PALETTE["bg"])
                tag_frame.grid(row=12, column=1, sticky="ew", padx=16, pady=6)
            tag_bg = PALETTE["entry_bg"] if show_tag_scroll else PALETTE["bg"]
            self.tag_vars = {}
            for tag in tags:
                var = tk.BooleanVar(value=False)
                tk.Checkbutton(tag_frame, text=tag["name"], variable=var,
                               fg=tag["color"], bg=tag_bg,
                               selectcolor=PALETTE["entry_bg"],
                               activebackground=tag_bg,
                               activeforeground=PALETTE["text"],
                               font=("Georgia", 9)).pack(anchor="w", padx=4)
                self.tag_vars[tag["id"]] = var
        else:
            self.tag_vars = {}

        # Row 13: Save / Cancel
        btn_row = tk.Frame(f, bg=PALETTE["bg"])
        btn_row.grid(row=13, column=0, columnspan=2, pady=(16,0))
        RoundedButton(btn_row, "Save", command=self._save,
                      width=100, height=32).pack(side="left", padx=6)
        RoundedButton(btn_row, "Cancel", command=self.destroy,
                      width=100, height=32, bg=PALETTE["text_dim"]).pack(side="left", padx=6)

    def _style_combo(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TCombobox",
                        fieldbackground=PALETTE["entry_bg"],
                        background=PALETTE["entry_bg"],
                        foreground=PALETTE["text"],
                        selectbackground=PALETTE["card"],
                        selectforeground=PALETTE["text"])

    def _set_rating(self, val):
        self.rating_var.set(val)
        for i, b in enumerate(self.star_btns):
            b.config(text="★" if i < val else "☆")

    def _set_cover(self, color):
        self.cover_color = color
        self.cover_preview.config(fg=color)

    def _set_cover_image(self, image_bytes):
        """Store image bytes and update the cover preview panel."""
        self._loaded_cover_image = image_bytes
        if not image_bytes:
            self._cover_lbl.config(image="", text="No\nCover")
            self._cover_lbl.image = None
            return
        photo = make_photo_image(image_bytes, 78, 110)
        if photo:
            self._cover_lbl.config(image=photo, text="")
            self._cover_lbl.image = photo  # prevent GC
        else:
            # Pillow not installed — show a hint
            self._cover_lbl.config(image="", text="Cover\nsaved\n(install\nPillow\nto view)")
            self._cover_lbl.image = None

    def _load(self, book_id):
        b = self.db.get_book(book_id)
        if not b:
            return
        self.vars["title"].set(b["title"])
        self.vars["author"].set(b["author"] or "")
        self.vars["genre"].set(b["genre"] or "")
        self.vars["year"].set(str(b["year"]) if b["year"] else "")
        self._isbn_var.set(b["isbn"] or "")
        self.status_var.set(b["status"])
        if b["rating"]:
            self._set_rating(b["rating"])
        if b["cover_color"]:
            self._set_cover(b["cover_color"])
        self.notes_text.insert("1.0", b["notes"] or "")
        self._set_cover_image(b["cover_image"])
        # store digital metadata for _save
        self._loaded_file_path  = b["file_path"]
        self._loaded_is_digital = b["is_digital"]
        # show file path if digital (row 10)
        if b["is_digital"] and b["file_path"]:
            short = b["file_path"]
            if len(short) > 52: short = "…" + short[-51:]
            self._file_path_lbl.config(text=short)
            self._file_path_row_label.grid(row=10, column=0, sticky="nw", padx=16, pady=4)
            self._file_path_lbl.grid(row=10, column=1, sticky="ew", padx=16, pady=4)
        current_shelves = {s["id"] for s in self.db.get_book_shelves(book_id)}
        for sid, var in self.shelf_vars.items():
            var.set(sid in current_shelves)
        current_tags = {t["id"] for t in self.db.get_book_tags(book_id)}
        for tid, var in self.tag_vars.items():
            var.set(tid in current_tags)

    def _apply_prefill(self, data: dict):
        """Pre-fill form fields from ISBN lookup data."""
        if data.get("title"):        self.vars["title"].set(data["title"])
        if data.get("author"):       self.vars["author"].set(data["author"])
        if data.get("genre"):        self.vars["genre"].set(data["genre"])
        if data.get("year"):         self.vars["year"].set(str(data["year"]))
        if data.get("isbn"):         self._isbn_var.set(data["isbn"])
        if "cover_image" in data:    self._set_cover_image(data["cover_image"])
        if data.get("description"):
            self.notes_text.delete("1.0", "end")
            self.notes_text.insert("1.0", data["description"])

    def _isbn_fetch(self):
        """Fetch book metadata from Open Library and populate fields."""
        isbn = self._isbn_var.get().strip()
        if not isbn:
            messagebox.showwarning("ISBN required", "Please enter an ISBN to look up.", parent=self)
            return

        # Disable button area and show spinner while fetching
        self._isbn_spinner.config(text="  ⟳ Fetching…", fg=PALETTE["warn"])
        self.update()

        def worker():
            try:
                data = fetch_book_by_isbn(isbn)
                # Schedule apply on main thread
                self.after(0, lambda: self._isbn_apply(data))
            except ValueError as e:
                err = str(e)
                self.after(0, lambda: self._isbn_error(err))

        threading.Thread(target=worker, daemon=True).start()

    def _isbn_apply(self, data: dict):
        """Apply fetched data into form fields and show a success message."""
        self._isbn_spinner.config(text="")
        if data.get("title"):        self.vars["title"].set(data["title"])
        if data.get("author"):       self.vars["author"].set(data["author"])
        if data.get("genre"):        self.vars["genre"].set(data["genre"])
        if data.get("year"):         self.vars["year"].set(str(data["year"]))
        if data.get("isbn"):         self._isbn_var.set(data["isbn"])
        if "cover_image" in data:    self._set_cover_image(data["cover_image"])
        if data.get("description"):
            self.notes_text.delete("1.0", "end")
            self.notes_text.insert("1.0", data["description"])

        filled = []
        if data.get("title"):        filled.append(f"Title: {data['title']}")
        if data.get("author"):       filled.append(f"Author: {data['author']}")
        if data.get("genre"):        filled.append(f"Genre: {data['genre']}")
        if data.get("year"):         filled.append(f"Year: {data['year']}")
        if data.get("cover_image"):  filled.append("Cover image: fetched ✓")
        if data.get("description"):  filled.append("Notes: (description added)")

        summary = "\n".join(filled) if filled else "No data returned."
        messagebox.showinfo("ISBN Lookup Successful",
                            f"Fields updated from Open Library:\n\n{summary}",
                            parent=self)

    def _isbn_error(self, message: str):
        """Show a clear error dialog when ISBN lookup fails."""
        self._isbn_spinner.config(text="")
        messagebox.showerror(
            "ISBN Lookup Failed",
            f"{message}\n\nCheck the ISBN and try again, or fill in the fields manually.",
            parent=self
        )

    def _save(self):
        title = self.vars["title"].get().strip()
        if not title:
            messagebox.showwarning("Required", "Title is required.", parent=self)
            return
        author = self.vars["author"].get().strip() or None
        genre  = self.vars["genre"].get().strip() or None
        year_s = self.vars["year"].get().strip()
        year   = int(year_s) if year_s.isdigit() else None
        isbn   = self._isbn_var.get().strip().replace("-", "").replace(" ", "").upper() or None
        rating = self.rating_var.get() or None
        status = self.status_var.get()
        notes  = self.notes_text.get("1.0", "end-1c").strip() or None

        if self.book_id:
            self.db.update_book(self.book_id, title, author, genre, year,
                                rating, status, notes, self.cover_color,
                                file_path=self._loaded_file_path,
                                is_digital=self._loaded_is_digital,
                                isbn=isbn,
                                cover_image=self._loaded_cover_image)
            bid = self.book_id
            current = {s["id"] for s in self.db.get_book_shelves(bid)}
            for sid, var in self.shelf_vars.items():
                if var.get() and sid not in current:
                    self.db.assign_book_to_shelf(bid, sid)
                elif not var.get() and sid in current:
                    self.db.remove_book_from_shelf(bid, sid)
            current_tags = {t["id"] for t in self.db.get_book_tags(bid)}
            for tid, var in self.tag_vars.items():
                if var.get() and tid not in current_tags:
                    self.db.assign_book_to_tag(bid, tid)
                elif not var.get() and tid in current_tags:
                    self.db.remove_book_from_tag(bid, tid)
        else:
            bid = self.db.add_book(title, author, genre, year,
                                   rating, status, notes, self.cover_color,
                                   isbn=isbn,
                                   cover_image=self._loaded_cover_image)
            for sid, var in self.shelf_vars.items():
                if var.get():
                    self.db.assign_book_to_shelf(bid, sid)
            for tid, var in self.tag_vars.items():
                if var.get():
                    self.db.assign_book_to_tag(bid, tid)

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
        for c in COVER_PRESETS:
            s = tk.Label(cf, bg=c, width=2, height=1, cursor="hand2", relief="flat")
            s.pack(side="left", padx=2)
            s.bind("<Button-1>", lambda e, col=c: self._pick(col))
        self.preview = tk.Label(f, text=" ▐  Color Preview", fg=self.chosen_color,
                                 bg=PALETTE["bg"], font=("Arial", 14))
        self.preview.pack(anchor="w", pady=6)
        btn = tk.Frame(f, bg=PALETTE["bg"])
        btn.pack(pady=(10,0))
        RoundedButton(btn, "Save", command=self._save,
                      width=90, height=30).pack(side="left", padx=4)
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


class TagDialog(tk.Toplevel):
    """Create or edit a category tag."""
    def __init__(self, parent, db, tag_id=None, on_save=None):
        super().__init__(parent)
        self.db = db
        self.tag_id = tag_id
        self.on_save = on_save
        self.chosen_color = "#FF9F0A"
        self.title("Edit Category" if tag_id else "New Category")
        self.configure(bg=PALETTE["bg"])
        self.resizable(False, False)
        self.grab_set()
        self._build()
        if tag_id:
            row = next((t for t in db.get_tags() if t["id"] == tag_id), None)
            if row:
                self.name_var.set(row["name"])
                self._pick(row["color"])
        self.geometry("+%d+%d" % (parent.winfo_rootx()+100, parent.winfo_rooty()+80))

    def _build(self):
        f = tk.Frame(self, bg=PALETTE["bg"], padx=24, pady=20)
        f.pack()
        tk.Label(f, text="Category Name", fg=PALETTE["text_dim"],
                 bg=PALETTE["bg"], font=("Courier", 9)).pack(anchor="w")
        self.name_var = tk.StringVar()
        tk.Entry(f, textvariable=self.name_var, bg=PALETTE["entry_bg"],
                 fg=PALETTE["text"], insertbackground=PALETTE["text"],
                 relief="flat", font=("Georgia", 11), width=24).pack(pady=(4, 12))
        tk.Label(f, text="Color", fg=PALETTE["text_dim"],
                 bg=PALETTE["bg"], font=("Courier", 9)).pack(anchor="w")
        cf = tk.Frame(f, bg=PALETTE["bg"])
        cf.pack(anchor="w", pady=4)
        for c in COVER_PRESETS:
            s = tk.Label(cf, bg=c, width=2, height=1, cursor="hand2", relief="flat")
            s.pack(side="left", padx=2)
            s.bind("<Button-1>", lambda e, col=c: self._pick(col))
        self.preview = tk.Label(f, text=" ▐  Color Preview", fg=self.chosen_color,
                                 bg=PALETTE["bg"], font=("Arial", 14))
        self.preview.pack(anchor="w", pady=6)
        btn = tk.Frame(f, bg=PALETTE["bg"])
        btn.pack(pady=(10, 0))
        RoundedButton(btn, "Save", command=self._save,
                      width=90, height=30).pack(side="left", padx=4)
        RoundedButton(btn, "Cancel", command=self.destroy,
                      width=90, height=30, bg=PALETTE["text_dim"]).pack(side="left", padx=4)

    def _pick(self, color):
        self.chosen_color = color
        self.preview.config(fg=color)

    def _save(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showwarning("Required", "Category name is required.", parent=self)
            return
        if self.tag_id:
            self.db.rename_tag(self.tag_id, name)
            self.db.update_tag_color(self.tag_id, self.chosen_color)
        else:
            self.db.add_tag(name, self.chosen_color)
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
        f.columnconfigure(0, weight=1)
        f.rowconfigure(4, weight=1)   # results row expands

        # Row 0 — header
        tk.Label(f, text="✦  AI Recommendations", fg=PALETTE["accent"],
                 bg=PALETTE["bg"], font=("Georgia", 14, "bold")
                 ).grid(row=0, column=0, sticky="w", pady=(0, 10))

        # Row 1 — mode selector
        mode_frame = tk.Frame(f, bg=PALETTE["bg"])
        mode_frame.grid(row=1, column=0, sticky="w", pady=(0, 8))
        tk.Label(mode_frame, text="Mode:", fg=PALETTE["text_dim"],
                 bg=PALETTE["bg"], font=("Courier", 9)).pack(side="left")
        self.mode = tk.StringVar(value="custom")
        for val, lbl in [("library", "Based on my library"), ("custom", "Custom request")]:
            tk.Radiobutton(mode_frame, text=lbl, variable=self.mode, value=val,
                           fg=PALETTE["text"], bg=PALETTE["bg"],
                           selectcolor=PALETTE["entry_bg"],
                           activebackground=PALETTE["bg"], font=("Georgia", 9),
                           command=self._toggle_mode).pack(side="left", padx=8)

        # Row 2 — prompt (hidden when mode == "library")
        self.prompt_frame = tk.Frame(f, bg=PALETTE["bg"])
        self.prompt_frame.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        tk.Label(self.prompt_frame, text="What would you like to read or learn?",
                 fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Courier", 9)).pack(anchor="w")
        self.prompt_text = tk.Text(self.prompt_frame, bg=PALETTE["entry_bg"],
                                    fg=PALETTE["text"],
                                    insertbackground=PALETTE["text"], relief="flat",
                                    font=("Georgia", 10), width=60, height=3)
        self.prompt_text.pack(fill="x", pady=(4, 0))

        # Row 3 — button row
        btn_row = tk.Frame(f, bg=PALETTE["bg"])
        btn_row.grid(row=3, column=0, sticky="w", pady=(0, 8))
        RoundedButton(btn_row, "Get Recommendations", command=self._ask,
                      width=180, height=32, font_size=9).pack(side="left")
        self.spinner = tk.Label(btn_row, text="", fg=PALETTE["warn"],
                                 bg=PALETTE["bg"], font=("Arial", 12))
        self.spinner.pack(side="left", padx=8)

        # Row 4 — results (expands to fill remaining space)
        tk.Label(f, text="Results", fg=PALETTE["text_dim"],
                 bg=PALETTE["bg"], font=("Courier", 9)
                 ).grid(row=4, column=0, sticky="w")
        result_frame = tk.Frame(f, bg=PALETTE["bg"])
        result_frame.grid(row=5, column=0, sticky="nsew", pady=(2, 0))
        f.rowconfigure(5, weight=1)
        self.result_box = tk.Text(result_frame, bg=PALETTE["entry_bg"],
                                   fg=PALETTE["text"],
                                   relief="flat", font=("Georgia", 10), wrap="word",
                                   state="disabled", padx=10, pady=10)
        sb = ttk.Scrollbar(result_frame, command=self.result_box.yview)
        self.result_box.config(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.result_box.pack(side="left", fill="both", expand=True)

    def _toggle_mode(self):
        if self.mode.get() == "library":
            # Hide the prompt row but keep its grid slot so nothing shifts
            self.prompt_frame.grid_remove()
        else:
            self.prompt_frame.grid()

    def _ask(self):
        if not ANTHROPIC_AVAILABLE:
            self._show("⚠ The 'anthropic' package is not installed.\nRun: pip install anthropic")
            return
        if not self.api_key:
            self._show("⚠ No API key set. Go to Settings → Set API Key.")
            return
        self.spinner.config(text="⟳ Thinking…")
        self.update()
        library_summary = self.db.get_all_books_summary()
        if self.mode.get() == "library":
            prompt = (f"Here is my personal library:\n{library_summary}\n\n"
                      f"Based on these books, recommend 5 books I would likely enjoy. "
                      f"For each, give the title, author, and a 1-2 sentence reason.")
        else:
            user_q = self.prompt_text.get("1.0", "end-1c").strip()
            if not user_q:
                self.spinner.config(text="")
                messagebox.showwarning("Empty", "Please enter a request.", parent=self)
                return
            prompt = (f"My current library:\n{library_summary}\n\n"
                      f"User request: {user_q}\n\n"
                      f"Recommend 5 books that match this request. "
                      f"For each, give the title, author, and a brief reason. "
                      f"Avoid recommending books already in the library.")

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


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

class AuthorProfileDialog(tk.Toplevel):
    """
    Popup showing author info sourced from Open Library.

    Matching strategy: search OL for the author name, then cross-reference
    each candidate's works against book titles already in the local library.
    The candidate whose works best overlap with the library wins.
    """

    OL_AUTHOR_SEARCH = "https://openlibrary.org/search/authors.json?q={}"
    OL_AUTHOR        = "https://openlibrary.org{}.json"
    OL_WORKS         = "https://openlibrary.org/authors/{}/works.json?limit=50"
    OL_PHOTO         = "https://covers.openlibrary.org/a/olid/{}-M.jpg"

    def __init__(self, parent, db, author_name):
        super().__init__(parent)
        self.db          = db
        self.author_name = author_name
        self.title(f"Author: {author_name}")
        self.configure(bg=PALETTE["bg"])
        self.resizable(True, True)
        self.geometry("520x600")
        self.grab_set()
        self._photo_image = None
        self._build_loading()
        self.geometry("+%d+%d" % (parent.winfo_rootx()+60, parent.winfo_rooty()+40))
        threading.Thread(target=self._fetch, daemon=True).start()

    def _build_loading(self):
        self._content_frame = tk.Frame(self, bg=PALETTE["bg"])
        self._content_frame.pack(fill="both", expand=True)
        tk.Label(self._content_frame,
                 text=f"\u29d0  Looking up {self.author_name}\u2026",
                 fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Georgia", 12, "italic")).pack(expand=True)

    @staticmethod
    def _get(url):
        req = urllib.request.Request(
            url, headers={"User-Agent": "PersonalLibraryManager/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return _json.loads(r.read().decode())

    @staticmethod
    def _title_key(title):
        import re
        t = (title or "").lower()
        t = re.sub(r"[^a-z0-9 ]", "", t)
        t = re.sub(r"\b(a|an|the)\b", "", t)
        return t.strip()

    def _titles_overlap(self, ol_titles, library_titles):
        def word_overlap(a, b):
            wa, wb = set(a.split()), set(b.split())
            if not wa or not wb:
                return 0.0
            return len(wa & wb) / max(len(wa), len(wb))
        ol_keys  = [self._title_key(t) for t in ol_titles]
        lib_keys = [self._title_key(t) for t in library_titles]
        score = 0
        for lk in lib_keys:
            if any(word_overlap(lk, ok) >= 0.8 for ok in ol_keys):
                score += 1
        return score

    def _fetch(self):
        lib_books  = self.db.get_books_by_author(self.author_name)
        lib_titles = [b["title"] for b in lib_books if b["title"]]
        author_data  = None
        photo_bytes  = None
        matched_score = 0
        try:
            q   = urllib.parse.quote(self.author_name)
            res = self._get(self.OL_AUTHOR_SEARCH.format(q))
            candidates = res.get("docs", [])[:8]
            best_olid  = None
            best_score = -1

            for cand in candidates:
                # The search API returns the bare OLID (e.g. "OL9388A") in "key"
                raw_key = cand.get("key", "")
                # Normalise: strip any leading path so we always have just "OL123A"
                olid = raw_key.replace("/authors/", "").strip("/")
                if not olid:
                    continue

                works_score = 0
                if lib_titles:
                    try:
                        works_data  = self._get(self.OL_WORKS.format(olid))
                        ol_titles   = [e.get("title", "")
                                       for e in works_data.get("entries", [])]
                        works_score = self._titles_overlap(ol_titles, lib_titles)
                    except Exception:
                        pass

                if works_score > best_score:
                    best_score = works_score
                    best_olid  = olid

            if best_olid is None and candidates:
                raw_key   = candidates[0].get("key", "")
                best_olid = raw_key.replace("/authors/", "").strip("/")

            if best_olid:
                matched_score = best_score
                # Fetch full author record: /authors/OL123A.json
                try:
                    author_url  = f"https://openlibrary.org/authors/{best_olid}.json"
                    author_data = self._get(author_url)
                except Exception:
                    pass

            if author_data:
                photos   = author_data.get("photos", [])
                photo_id = photos[0] if photos else None
                if photo_id and photo_id > 0:
                    photo_url = f"https://covers.openlibrary.org/a/id/{photo_id}-M.jpg"
                else:
                    photo_url = self.OL_PHOTO.format(best_olid)
                try:
                    req = urllib.request.Request(
                        photo_url,
                        headers={"User-Agent": "PersonalLibraryManager/1.0"})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        raw = r.read()
                    if len(raw) > 1000:
                        photo_bytes = raw
                except Exception:
                    pass
                # Store the OLID so _render can build the OL link
                author_data["_olid"] = best_olid

        except Exception:
            pass
        self.after(0, lambda: self._render(author_data, photo_bytes, matched_score))

    def _render(self, data, photo_bytes, matched_score):
        for w in self._content_frame.winfo_children():
            w.destroy()
        P  = PALETTE
        cf = self._content_frame
        cf.config(bg=P["bg"])

        canvas = tk.Canvas(cf, bg=P["bg"], highlightthickness=0)
        sb     = ttk.Scrollbar(cf, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        body   = tk.Frame(canvas, bg=P["bg"])
        win_id = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind("<Configure>",
                  lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(win_id, width=e.width))
        for w in (canvas, body):
            w.bind("<MouseWheel>",
                   lambda e: canvas.yview_scroll(-1*(e.delta//120), "units"))

        lib_books = self.db.get_books_by_author(self.author_name)
        if lib_books and matched_score == 0 and data:
            tk.Label(body,
                     text="\u26a0  Could not verify this matches your author \u2014 "
                          "none of their Open Library works matched your books.",
                     fg=P["warn"], bg=P["bg"], font=("Courier", 8),
                     wraplength=460, justify="left"
                     ).pack(anchor="w", padx=20, pady=(14, 0))

        header = tk.Frame(body, bg=P["bg"])
        header.pack(fill="x", padx=20, pady=(18, 6))

        if photo_bytes and PIL_AVAILABLE:
            try:
                img   = Image.open(_io.BytesIO(photo_bytes))
                img.thumbnail((110, 150), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._photo_image = photo
                tk.Label(header, image=photo, bg=P["bg"], bd=0
                         ).pack(side="left", anchor="n", padx=(0, 16))
            except Exception:
                pass

        name_block = tk.Frame(header, bg=P["bg"])
        name_block.pack(side="left", fill="both", expand=True, anchor="n")
        tk.Label(name_block, text=self.author_name,
                 fg=P["text"], bg=P["bg"],
                 font=("Georgia", 16, "bold"),
                 wraplength=310, justify="left").pack(anchor="w")

        if data:
            born  = data.get("birth_date", "")
            died  = data.get("death_date", "")
            dates = "  \u00b7  ".join(filter(None, [
                f"b. {born}" if born else "",
                f"d. {died}" if died else "",
            ]))
            if dates:
                tk.Label(name_block, text=dates,
                         fg=P["text_dim"], bg=P["bg"],
                         font=("Courier", 9)).pack(anchor="w", pady=(3, 0))
            ol_key = data.get("_olid", "") or data.get("key", "")
            if ol_key:
                # _olid is just "OL123A"; key from record is "/authors/OL123A"
                olid   = ol_key.replace("/authors/", "").strip("/")
                ol_url = f"https://openlibrary.org/authors/{olid}"
                link   = tk.Label(name_block, text="\u2197 Open Library",
                                  fg=P["text_dim"], bg=P["bg"],
                                  font=("Courier", 8), cursor="hand2")
                link.pack(anchor="w", pady=(4, 0))
                link.bind("<Button-1>", lambda e, u=ol_url: self._open_url(u))
        else:
            tk.Label(name_block,
                     text="No profile found on Open Library.",
                     fg=P["text_dim"], bg=P["bg"],
                     font=("Courier", 9, "italic")).pack(anchor="w", pady=(4, 0))

        tk.Frame(body, bg=P["border"], height=1).pack(fill="x", padx=20, pady=(8, 0))

        if data:
            bio_raw = data.get("bio", "")
            if isinstance(bio_raw, dict):
                bio_raw = bio_raw.get("value", "")
            if bio_raw:
                tk.Label(body, text="BIOGRAPHY", fg=P["text_dim"], bg=P["bg"],
                         font=("Courier", 8, "bold")
                         ).pack(anchor="w", padx=20, pady=(12, 4))
                import re as _re
                sentences = _re.split(r'(?<=[.!?])\s+', bio_raw.strip())
                short_bio = " ".join(sentences[:4])
                if len(sentences) > 4:
                    short_bio += " \u2026"
                tk.Label(body, text=short_bio,
                         fg=P["text"], bg=P["bg"],
                         font=("Georgia", 10), wraplength=460,
                         justify="left").pack(anchor="w", padx=20, pady=(0, 10))

        tk.Frame(body, bg=P["border"], height=1).pack(fill="x", padx=20)

        tk.Label(body, text="IN YOUR LIBRARY", fg=P["text_dim"], bg=P["bg"],
                 font=("Courier", 8, "bold")).pack(anchor="w", padx=20, pady=(12, 4))

        if lib_books:
            books_sorted = sorted(lib_books,
                key=lambda b: (-(b["rating"] or 0), (b["title"] or "").lower()))
            for b in books_sorted:
                row = tk.Frame(body, bg=P["card"],
                               highlightbackground=P["border"],
                               highlightthickness=1)
                row.pack(fill="x", padx=20, pady=2)
                left = tk.Frame(row, bg=P["card"])
                left.pack(side="left", fill="both", expand=True, padx=10, pady=6)
                tk.Label(left, text=b["title"],
                         fg=P["text"], bg=P["card"],
                         font=("Georgia", 10, "bold"),
                         anchor="w", justify="left").pack(anchor="w")
                meta = tk.Frame(left, bg=P["card"])
                meta.pack(anchor="w")
                if b["rating"]:
                    stars = "\u2605" * b["rating"] + "\u2606" * (5 - b["rating"])
                    tk.Label(meta, text=stars, fg=P["warn"],
                             bg=P["card"], font=("Arial", 10)).pack(side="left")
                sc = STATUS_COLORS.get(b["status"], P["text_dim"])
                tk.Label(meta, text=f"  {b['status'].upper()}",
                         fg=sc, bg=P["card"],
                         font=("Courier", 8, "bold")).pack(side="left")
                if b["genre"]:
                    tk.Label(meta, text=f"  {b['genre']}",
                             fg=P["text_dim"], bg=P["card"],
                             font=("Courier", 8)).pack(side="left")
        else:
            tk.Label(body, text="No books by this author in your library yet.",
                     fg=P["text_dim"], bg=P["bg"],
                     font=("Georgia", 10, "italic")).pack(anchor="w", padx=20, pady=6)

        tk.Frame(body, bg=P["border"], height=1).pack(fill="x", padx=20, pady=(14, 0))
        RoundedButton(body, "Close", command=self.destroy,
                      width=90, height=30, bg=P["text_dim"],
                      font_size=9).pack(pady=14)

    @staticmethod
    def _open_url(url):
        import webbrowser
        webbrowser.open(url)


class Wiborada(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Personal Library")
        self.minsize(900, 600)
        self.geometry("1100x680")

        self.db = Database()
        self.current_shelf   = None
        self.current_tag     = None
        self.current_author  = None
        self._detail_book_id = None
        self._search_has_placeholder = True
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self.refresh_books()
                                  if hasattr(self, "book_frame") else None)

        # load saved theme
        saved = self.db.get_setting("theme", "dark")
        self._current_theme = saved
        apply_theme(saved)
        self.configure(bg=PALETTE["bg"])

        self._build_layout()
        self.refresh_shelves()
        self.refresh_books()
        self.refresh_stats()

    # ── layout ────────────────────────────────────────────────────────────────
    def _build_layout(self):
        # top bar
        self.topbar = tk.Frame(self, bg=PALETTE["topbar"], height=52)
        self.topbar.pack(side="top", fill="x")
        self.topbar.pack_propagate(False)

        self.title_lbl = tk.Label(self.topbar, text="📚  Personal Library",
                                   fg="#FFFFFF", bg=PALETTE["topbar"],
                                   font=("Georgia", 15, "bold"))
        self.title_lbl.pack(side="left", padx=18)

        search_frame = tk.Frame(self.topbar, bg=PALETTE["topbar"])
        search_frame.pack(side="left", padx=20)

        PLACEHOLDER = "🔍  Search books…"
        self.search_entry = tk.Entry(search_frame, textvariable=self.search_var,
                                      bg="#3A3A3C", fg="#8E8E93",
                                      insertbackground="#F2F2F7", relief="flat",
                                      font=("Georgia", 10), width=26)
        self.search_entry.pack(ipady=5, padx=4)
        self.search_entry.insert(0, PLACEHOLDER)
        self._search_has_placeholder = True

        def _search_focus_in(e):
            if self._search_has_placeholder:
                self.search_entry.delete(0, "end")
                self.search_entry.config(fg="#F2F2F7")
                self._search_has_placeholder = False

        def _search_focus_out(e):
            if not self.search_entry.get():
                self.search_entry.insert(0, PLACEHOLDER)
                self.search_entry.config(fg="#8E8E93")
                self._search_has_placeholder = True

        self.search_entry.bind("<FocusIn>",  _search_focus_in)
        self.search_entry.bind("<FocusOut>", _search_focus_out)

        # theme toggle button (moon/sun)
        _theme_btn_bg = "#FAF7F2" if self._current_theme == "dark" else "#2C2C2E"
        self.theme_btn = RoundedButton(
            self.topbar,
            text="☀ Light" if self._current_theme == "dark" else "🌙 Dark",
            command=self._toggle_theme,
            width=90, height=30, bg=_theme_btn_bg,
            fg="#2E2416" if self._current_theme == "dark" else "#F2F2F7",
            font_size=9
        )
        self.theme_btn.pack(side="right", padx=8, pady=10)

        self.settings_btn = RoundedButton(self.topbar, "⚙ Settings",
                                           command=self._open_settings,
                                           width=100, height=30,
                                           bg="#5B7FA6", font_size=9)
        self.settings_btn.pack(side="right", padx=4, pady=10)

        self.recs_btn = RoundedButton(self.topbar, "✦ AI Recs",
                                       command=self._open_recs,
                                       width=100, height=30,
                                       bg="#7B82C4", font_size=9)
        self.recs_btn.pack(side="right", padx=4, pady=10)

        self.add_btn = RoundedButton(
            self.topbar, "+ Add Book",
            command=self._add_book_picker,
            width=110, height=30, font_size=9
        )
        self.add_btn.pack(side="right", padx=4, pady=10)

        # stats bar
        self.stats_bar = tk.Frame(self, bg=PALETTE["statsbar"], height=32)
        self.stats_bar.pack(side="top", fill="x")
        self.stats_bar.pack_propagate(False)
        self.stats_labels = {}
        for key in ["total", "read", "reading", "unread"]:
            lbl = tk.Label(self.stats_bar, text="", fg=PALETTE["text_dim"],
                           bg=PALETTE["statsbar"], font=("Courier", 9))
            lbl.pack(side="left", padx=14)
            self.stats_labels[key] = lbl

        # body
        self.body = tk.Frame(self, bg=PALETTE["bg"])
        self.body.pack(side="top", fill="both", expand=True)

        # sidebar
        self.sidebar = tk.Frame(self.body, bg=PALETTE["sidebar"], width=260)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        # main panel
        self.main_panel = tk.Frame(self.body, bg=PALETTE["bg"])
        self.main_panel.pack(side="left", fill="both", expand=True)
        self._build_main()

        # Now both sidebar and main are ready — populate sidebar
        self._set_view_mode("shelves")

    def _build_sidebar(self):
        # ── mode tabs ─────────────────────────────────────────────────────────
        self._tab_bar = tk.Frame(self.sidebar, bg=PALETTE["sidebar"])
        self._tab_bar.pack(fill="x", padx=4, pady=(10, 0))
        self._view_mode   = "shelves"   # "shelves" | "categories" | "authors"
        self._tab_labels  = {}
        for mode, label in [("shelves", "Shelves"),
                             ("categories", "Categories"),
                             ("authors", "Authors")]:
            lbl = tk.Label(self._tab_bar, text=label, fg=PALETTE["text_dim"],
                           bg=PALETTE["sidebar"], font=("Courier", 8, "bold"),
                           cursor="hand2", padx=6, pady=4)
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, m=mode: self._set_view_mode(m))
            self._tab_labels[mode] = lbl

        # thin divider under tabs
        self._tab_divider = tk.Frame(self.sidebar, bg=PALETTE["border"], height=1)
        self._tab_divider.pack(fill="x", padx=4)

        # ── scrollable list area ──────────────────────────────────────────────
        self.shelf_list_frame = tk.Frame(self.sidebar, bg=PALETTE["sidebar"])
        self.shelf_list_frame.pack(fill="both", expand=True, padx=6)

        # ── bottom action button ──────────────────────────────────────────────
        self._sidebar_action_frame = tk.Frame(self.sidebar, bg=PALETTE["sidebar"])
        self._sidebar_action_frame.pack(pady=8)
        # Initial populate is deferred until after _build_main creates shelf_title

    def _set_view_mode(self, mode):
        self._view_mode = mode
        # update tab highlight
        for m, lbl in self._tab_labels.items():
            if m == mode:
                lbl.config(fg=PALETTE["accent"], bg=PALETTE["card"])
            else:
                lbl.config(fg=PALETTE["text_dim"], bg=PALETTE["sidebar"])
        # clear selection state
        self.current_shelf  = None
        self.current_tag    = None
        self.current_author = None
        self.shelf_title.config(text="All Books")
        # rebuild list + bottom button
        self._rebuild_sidebar_list()

    def _rebuild_sidebar_list(self):
        """Repopulate the sidebar list and action button for the current view mode."""
        for w in self.shelf_list_frame.winfo_children():
            w.destroy()
        for w in self._sidebar_action_frame.winfo_children():
            w.destroy()

        mode = self._view_mode

        if mode == "shelves":
            self._sidebar_all_row("📚  All Books",
                                   lambda: self._select_shelf(None))
            for shelf in self.db.get_shelves():
                self._shelf_row(shelf)
            RoundedButton(self._sidebar_action_frame, "+ New Shelf",
                          command=lambda: ShelfDialog(self, self.db,
                                                       on_save=self.refresh_shelves),
                          width=160, height=28, bg=PALETTE["border"],
                          fg=PALETTE["text"], font_size=9).pack()

        elif mode == "categories":
            self._sidebar_all_row("🏷  All Books",
                                   lambda: self._select_tag(None))
            for tag in self.db.get_tags():
                self._tag_row(tag)
            RoundedButton(self._sidebar_action_frame, "+ New Category",
                          command=lambda: TagDialog(self, self.db,
                                                     on_save=self.refresh_shelves),
                          width=160, height=28, bg=PALETTE["border"],
                          fg=PALETTE["text"], font_size=9).pack()

        elif mode == "authors":
            self._sidebar_all_row("👤  All Books",
                                   lambda: self._select_author(None))
            for author in self.db.get_authors():
                self._author_row(author)
            # no add-button for authors (auto-derived)

        self.refresh_books()

    def _sidebar_all_row(self, label_text, callback):
        row = tk.Frame(self.shelf_list_frame, bg=PALETTE["sidebar"], cursor="hand2")
        row.pack(fill="x", pady=1)
        lbl = tk.Label(row, text=f"  {label_text}", fg=PALETTE["text"],
                       bg=PALETTE["sidebar"], font=("Georgia", 10), anchor="w")
        lbl.pack(side="left", fill="x", expand=True)
        for w in [row, lbl]:
            w.bind("<Button-1>", lambda e: callback())

    def _shelf_row(self, shelf):
        row = tk.Frame(self.shelf_list_frame, bg=PALETTE["sidebar"], cursor="hand2")
        row.pack(fill="x", pady=1)
        dot = tk.Label(row, text=" ● ", fg=shelf["color"],
                       bg=PALETTE["sidebar"], font=("Arial", 10))
        dot.pack(side="left")
        name_lbl = tk.Label(row, text=shelf["name"], fg=PALETTE["text"],
                             bg=PALETTE["sidebar"], font=("Georgia", 10), anchor="w")
        name_lbl.pack(side="left", fill="x", expand=True)
        ctx = tk.Label(row, text="⋯", fg=PALETTE["text_dim"],
                       bg=PALETTE["sidebar"], font=("Arial", 12), cursor="hand2")
        ctx.pack(side="right", padx=4)
        def show_menu(e, sid=shelf["id"]):
            m = tk.Menu(self, tearoff=0, bg=PALETTE["menu_bg"], fg=PALETTE["text"],
                        activebackground=PALETTE["accent"],
                        activeforeground="white", relief="flat")
            m.add_command(label="Edit Shelf",
                          command=lambda: ShelfDialog(self, self.db, sid,
                                                       on_save=self.refresh_shelves))
            m.add_command(label="Delete Shelf",
                          command=lambda: self._delete_shelf(sid))
            m.post(e.x_root, e.y_root)
        ctx.bind("<Button-1>", show_menu)
        for w in [row, dot, name_lbl]:
            w.bind("<Button-1>", lambda e, sid=shelf["id"]: self._select_shelf(sid))

    def _tag_row(self, tag):
        row = tk.Frame(self.shelf_list_frame, bg=PALETTE["sidebar"], cursor="hand2")
        row.pack(fill="x", pady=1)
        dot = tk.Label(row, text=" ● ", fg=tag["color"],
                       bg=PALETTE["sidebar"], font=("Arial", 10))
        dot.pack(side="left")
        name_lbl = tk.Label(row, text=tag["name"], fg=PALETTE["text"],
                             bg=PALETTE["sidebar"], font=("Georgia", 10), anchor="w")
        name_lbl.pack(side="left", fill="x", expand=True)
        ctx = tk.Label(row, text="⋯", fg=PALETTE["text_dim"],
                       bg=PALETTE["sidebar"], font=("Arial", 12), cursor="hand2")
        ctx.pack(side="right", padx=4)
        def show_menu(e, tid=tag["id"]):
            m = tk.Menu(self, tearoff=0, bg=PALETTE["menu_bg"], fg=PALETTE["text"],
                        activebackground=PALETTE["accent"],
                        activeforeground="white", relief="flat")
            m.add_command(label="Edit Category",
                          command=lambda: TagDialog(self, self.db, tid,
                                                     on_save=self.refresh_shelves))
            m.add_command(label="Delete Category",
                          command=lambda: self._delete_tag(tid))
            m.post(e.x_root, e.y_root)
        ctx.bind("<Button-1>", show_menu)
        for w in [row, dot, name_lbl]:
            w.bind("<Button-1>", lambda e, tid=tag["id"]: self._select_tag(tid))

    def _author_row(self, author):
        row = tk.Frame(self.shelf_list_frame, bg=PALETTE["sidebar"], cursor="hand2")
        row.pack(fill="x", pady=1)
        tk.Label(row, text=" 📖 ", bg=PALETTE["sidebar"],
                 font=("Arial", 9)).pack(side="left")
        name_lbl = tk.Label(row, text=author, fg=PALETTE["text"],
                             bg=PALETTE["sidebar"], font=("Georgia", 10),
                             anchor="w", wraplength=170, justify="left")
        name_lbl.pack(side="left", fill="x", expand=True, padx=(0, 2))
        info_btn = tk.Label(row, text="ℹ", fg=PALETTE["accent"],
                            bg=PALETTE["sidebar"], font=("Arial", 11),
                            cursor="hand2", padx=4)
        info_btn.pack(side="right")
        info_btn.bind("<Button-1>",
                      lambda e, a=author: (e.widget.winfo_toplevel(),
                                           AuthorProfileDialog(self, self.db, a)))
        for w in [row, name_lbl]:
            w.bind("<Button-1>", lambda e, a=author: self._select_author(a))

    def _select_shelf(self, shelf_id):
        self.current_shelf  = shelf_id
        self.current_tag    = None
        self.current_author = None
        if shelf_id is None:
            self.shelf_title.config(text="All Books")
        else:
            shelf = next((s for s in self.db.get_shelves() if s["id"] == shelf_id), None)
            self.shelf_title.config(text=shelf["name"] if shelf else "Shelf")
        self.refresh_books()

    def _select_tag(self, tag_id):
        self.current_shelf  = None
        self.current_tag    = tag_id
        self.current_author = None
        if tag_id is None:
            self.shelf_title.config(text="All Books")
        else:
            tag = next((t for t in self.db.get_tags() if t["id"] == tag_id), None)
            self.shelf_title.config(text=f"🏷 {tag['name']}" if tag else "Category")
        self.refresh_books()

    def _select_author(self, author):
        self.current_shelf  = None
        self.current_tag    = None
        self.current_author = author
        self.shelf_title.config(text=f"👤 {author}" if author else "All Books")
        self.refresh_books()

    def _build_main(self):
        # ── filter bar ────────────────────────────────────────────────────────
        self.filter_bar = tk.Frame(self.main_panel, bg=PALETTE["bg"], padx=16, pady=8)
        self.filter_bar.pack(side="top", fill="x")
        self.shelf_title = tk.Label(self.filter_bar, text="All Books", fg=PALETTE["text"],
                                     bg=PALETTE["bg"], font=("Georgia", 13, "bold"))
        self.shelf_title.pack(side="left")

        self.status_filter = tk.StringVar(value="all")
        self._filter_radios = []
        for val, lbl in [("all","All"),("unread","Unread"),
                          ("reading","Reading"),("read","Read"),
                          ("wishlist","Wishlist"),("digital","Digital")]:
            color = STATUS_COLORS.get(val, PALETTE["text_dim"]) if val != "all" else PALETTE["text_dim"]
            rb = tk.Radiobutton(self.filter_bar, text=lbl, variable=self.status_filter,
                                value=val, fg=color, bg=PALETTE["bg"],
                                selectcolor=PALETTE["entry_bg"],
                                activebackground=PALETTE["bg"],
                                font=("Courier", 8, "bold"),
                                command=self.refresh_books)
            rb.pack(side="right", padx=4)
            self._filter_radios.append(rb)

        # ── two-column body: list | detail ────────────────────────────────────
        self.cols = tk.Frame(self.main_panel, bg=PALETTE["bg"])
        self.cols.pack(side="top", fill="both", expand=True, padx=10, pady=4)

        # Left: scrollable book list (fixed width)
        self.list_col = tk.Frame(self.cols, bg=PALETTE["bg"], width=320)
        self.list_col.pack(side="left", fill="y")
        self.list_col.pack_propagate(False)

        self._scroll_canvas = tk.Canvas(self.list_col, bg=PALETTE["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.list_col, orient="vertical",
                                   command=self._scroll_canvas.yview)
        self.book_frame = tk.Frame(self._scroll_canvas, bg=PALETTE["bg"])
        self.book_frame.bind("<Configure>",
                              lambda e: self._scroll_canvas.configure(
                                  scrollregion=self._scroll_canvas.bbox("all")))
        self._scroll_canvas.create_window((0, 0), window=self.book_frame, anchor="nw")
        self._scroll_canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._scroll_canvas.pack(side="left", fill="both", expand=True)

        # Bind scroll events on the canvas itself (Linux / macOS)
        self._scroll_canvas.bind("<Button-4>",
            lambda e: self._scroll_canvas.yview_scroll(-1, "units"))
        self._scroll_canvas.bind("<Button-5>",
            lambda e: self._scroll_canvas.yview_scroll(1, "units"))

        # Windows: bind_all so the event fires regardless of which child widget
        # the cursor is hovering over, then forward only when over the list area.
        def _on_mousewheel(event):
            widget = event.widget
            # Walk up the widget tree to see if we're inside list_col
            w = widget
            while w is not None:
                if w is self.list_col:
                    self._scroll_canvas.yview_scroll(-1 * (event.delta // 120), "units")
                    return
                try:
                    w = w.master
                except Exception:
                    break

        self.bind_all("<MouseWheel>", _on_mousewheel)

        # Divider
        self.cols_divider = tk.Frame(self.cols, bg=PALETTE["border"], width=1)
        self.cols_divider.pack(side="left", fill="y", padx=(4,0))

        # Right: detail panel
        self.detail_panel = tk.Frame(self.cols, bg=PALETTE["bg"])
        self.detail_panel.pack(side="left", fill="both", expand=True)
        self._detail_book_id = None
        self._show_detail_empty()

    # ── detail panel ─────────────────────────────────────────────────────────
    def _show_detail_empty(self):
        for w in self.detail_panel.winfo_children():
            w.destroy()
        self._detail_book_id = None
        tk.Label(self.detail_panel,
                 text="Select a book to\nsee its details",
                 fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Georgia", 12, "italic"), justify="center"
                 ).place(relx=0.5, rely=0.4, anchor="center")

    def _show_detail(self, book_id):
        b = self.db.get_book(book_id)
        if not b:
            return
        self._detail_book_id = book_id
        for w in self.detail_panel.winfo_children():
            w.destroy()

        P = PALETTE
        outer = tk.Frame(self.detail_panel, bg=P["bg"])
        outer.pack(fill="both", expand=True, padx=20, pady=18)

        # ── cover + title block ───────────────────────────────────────────
        top = tk.Frame(outer, bg=P["bg"])
        top.pack(fill="x", pady=(0, 14))

        if b["cover_image"]:
            photo = make_photo_image(b["cover_image"], 90, 130)
            if photo:
                img_lbl = tk.Label(top, image=photo, bg=P["bg"], bd=0,
                                   cursor="hand2")
                img_lbl.image = photo
                img_lbl.pack(side="left", anchor="n", padx=(0, 16))
                img_lbl.bind("<Button-1>",
                             lambda e, raw=b["cover_image"], title=b["title"]:
                             self._show_cover_fullsize(raw, title))
        elif b["cover_color"]:
            tk.Frame(top, bg=b["cover_color"], width=12).pack(side="left", fill="y",
                                                               padx=(0, 16))

        title_block = tk.Frame(top, bg=P["bg"])
        title_block.pack(side="left", fill="both", expand=True)

        tk.Label(title_block, text=b["title"], fg=P["text"], bg=P["bg"],
                 font=("Georgia", 15, "bold"), wraplength=260,
                 justify="left", anchor="w").pack(anchor="w")

        if b["author"]:
            author_row = tk.Frame(title_block, bg=P["bg"])
            author_row.pack(anchor="w", pady=(2, 0))
            tk.Label(author_row, text=f"by {b['author']}", fg=P["text_dim"],
                     bg=P["bg"], font=("Georgia", 10, "italic"),
                     anchor="w").pack(side="left")
            info_btn = tk.Label(author_row, text=" ℹ", fg=P["accent"],
                                bg=P["bg"], font=("Arial", 11), cursor="hand2")
            info_btn.pack(side="left")
            info_btn.bind("<Button-1>",
                          lambda e, a=b["author"]:
                          AuthorProfileDialog(self, self.db, a))

        if b["rating"]:
            stars = "★" * b["rating"] + "☆" * (5 - b["rating"])
            tk.Label(title_block, text=stars, fg=P["warn"],
                     bg=P["bg"], font=("Arial", 14)).pack(anchor="w", pady=(4, 0))

        # ── meta pills row ────────────────────────────────────────────────
        meta_row = tk.Frame(outer, bg=P["bg"])
        meta_row.pack(anchor="w", pady=(0, 10))

        def _pill(parent, text, color):
            tk.Label(parent, text=text, fg=color, bg=P["card"],
                     font=("Courier", 8, "bold"),
                     padx=8, pady=3, relief="flat").pack(side="left", padx=(0, 6))

        status_color = STATUS_COLORS.get(b["status"], P["text_dim"])
        _pill(meta_row, b["status"].upper(), status_color)
        if b["is_digital"]:
            ext = ""
            if b["file_path"]:
                ext = os.path.splitext(b["file_path"])[1].upper().lstrip(".")
            _pill(meta_row, ext or "DIGITAL", STATUS_COLORS["digital"])
        if b["genre"]:
            tk.Label(meta_row, text=b["genre"], fg=P["text_dim"], bg=P["bg"],
                     font=("Courier", 8)).pack(side="left", padx=(0, 8))
        if b["year"]:
            tk.Label(meta_row, text=str(b["year"]), fg=P["text_dim"], bg=P["bg"],
                     font=("Courier", 8)).pack(side="left", padx=(0, 8))
        if b["isbn"]:
            tk.Label(meta_row, text=f"ISBN {b['isbn']}", fg=P["text_dim"], bg=P["bg"],
                     font=("Courier", 8)).pack(side="left")

        # ── divider ───────────────────────────────────────────────────────
        tk.Frame(outer, bg=P["border"], height=1).pack(fill="x", pady=(0, 10))

        # ── notes ─────────────────────────────────────────────────────────
        if b["notes"]:
            tk.Label(outer, text="NOTES", fg=P["text_dim"], bg=P["bg"],
                     font=("Courier", 8, "bold")).pack(anchor="w")
            tk.Label(outer, text=b["notes"], fg=P["text"], bg=P["bg"],
                     font=("Georgia", 10), wraplength=300,
                     justify="left", anchor="w").pack(anchor="w", pady=(4, 12))

        # ── shelves ───────────────────────────────────────────────────────
        shelves = self.db.get_book_shelves(book_id)
        if shelves:
            tk.Label(outer, text="SHELVES", fg=P["text_dim"], bg=P["bg"],
                     font=("Courier", 8, "bold")).pack(anchor="w")
            shelf_row = tk.Frame(outer, bg=P["bg"])
            shelf_row.pack(anchor="w", pady=(4, 12))
            for s in shelves:
                tk.Label(shelf_row, text=f"● {s['name']}", fg=s["color"],
                         bg=P["bg"], font=("Georgia", 9)).pack(side="left", padx=(0, 10))

        # ── categories ────────────────────────────────────────────────────────
        book_tags = self.db.get_book_tags(book_id)
        if book_tags:
            tk.Label(outer, text="CATEGORIES", fg=P["text_dim"], bg=P["bg"],
                     font=("Courier", 8, "bold")).pack(anchor="w")
            tag_row = tk.Frame(outer, bg=P["bg"])
            tag_row.pack(anchor="w", pady=(4, 12))
            for t in book_tags:
                tk.Label(tag_row, text=f"🏷 {t['name']}", fg=t["color"],
                         bg=P["bg"], font=("Georgia", 9)).pack(side="left", padx=(0, 10))

        # ── file path (digital) ───────────────────────────────────────────
        if b["is_digital"] and b["file_path"]:
            tk.Label(outer, text="FILE", fg=P["text_dim"], bg=P["bg"],
                     font=("Courier", 8, "bold")).pack(anchor="w")
            short = b["file_path"]
            if len(short) > 55: short = "…" + short[-54:]
            tk.Label(outer, text=short, fg=STATUS_COLORS["digital"], bg=P["bg"],
                     font=("Courier", 8), wraplength=300,
                     justify="left", anchor="w").pack(anchor="w", pady=(4, 12))

        # ── action buttons ────────────────────────────────────────────────
        btn_row = tk.Frame(outer, bg=P["bg"])
        btn_row.pack(anchor="w", pady=(6, 0))

        RoundedButton(btn_row, "✏ Edit", width=90, height=30, font_size=9,
                      command=lambda: self._edit_book(book_id)).pack(side="left", padx=(0, 8))

        if b["is_digital"] and b["file_path"]:
            RoundedButton(btn_row, "▶ Open", width=90, height=30, font_size=9,
                          bg=STATUS_COLORS["digital"],
                          command=lambda: self._open_book_file(book_id)).pack(side="left", padx=(0, 8))

        RoundedButton(btn_row, "🗑 Delete", width=90, height=30, font_size=9,
                      bg=PALETTE["accent"],
                      command=lambda: self._delete_book(book_id)).pack(side="left")

    def _show_cover_fullsize(self, image_bytes, title=""):
        """Pop up a window showing the cover at full / natural size."""
        if not PIL_AVAILABLE or not image_bytes:
            messagebox.showinfo("No preview",
                                "Install Pillow to view full-size covers.\n"
                                "Run: pip install Pillow", parent=self)
            return

        try:
            img = Image.open(_io.BytesIO(image_bytes))
        except Exception as e:
            messagebox.showerror("Image error", str(e), parent=self)
            return

        # Scale to fit within 80% of the screen, keeping aspect ratio
        sw = int(self.winfo_screenwidth()  * 0.80)
        sh = int(self.winfo_screenheight() * 0.80)
        img.thumbnail((sw, sh), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img)

        win = tk.Toplevel(self)
        win.title(title or "Cover")
        win.configure(bg="#000000")
        win.resizable(False, False)

        lbl = tk.Label(win, image=photo, bg="#000000", cursor="hand2")
        lbl.image = photo
        lbl.pack()
        lbl.bind("<Button-1>", lambda e: win.destroy())

        tk.Label(win, text="Click image to close",
                 fg="#555555", bg="#000000",
                 font=("Courier", 8)).pack(pady=(0, 6))

        # Centre on screen
        win.update_idletasks()
        x = (self.winfo_screenwidth()  - win.winfo_width())  // 2
        y = (self.winfo_screenheight() - win.winfo_height()) // 2
        win.geometry(f"+{x}+{y}")
        win.grab_set()

    # ── theme switching ───────────────────────────────────────────────────────
    def _toggle_theme(self):
        new_theme = "light" if self._current_theme == "dark" else "dark"
        self._current_theme = new_theme
        apply_theme(new_theme)
        self.db.set_setting("theme", new_theme)
        self._repaint_all()

    def _repaint_all(self):
        """Repaint the entire UI with the current PALETTE without rebuilding data."""
        P = PALETTE

        # root
        self.configure(bg=P["bg"])

        # topbar — always white text (both themes use a dark topbar)
        self.topbar.config(bg=P["topbar"])
        self.title_lbl.config(fg="#FFFFFF", bg=P["topbar"])
        for child in self.topbar.winfo_children():
            if isinstance(child, tk.Frame):
                child.config(bg=P["topbar"])
                for gc in child.winfo_children():
                    if gc is self.search_entry:
                        continue   # search bar stays dark regardless of theme
                    try: gc.config(bg=P["entry_bg"], fg=P["text"],
                                   insertbackground=P["text"])
                    except Exception: pass

        # theme button — cream when showing "Light", dark-gray when showing "Dark"
        is_dark = self._current_theme == "dark"
        self.theme_btn.text_val  = "☀ Light" if is_dark else "🌙 Dark"
        self.theme_btn._btn_bg   = "#FAF7F2" if is_dark else "#2C2C2E"
        self.theme_btn._normal_bg = self.theme_btn._btn_bg
        self.theme_btn._hover_bg  = self.theme_btn._darken(self.theme_btn._btn_bg)
        self.theme_btn.fg         = "#2E2416" if is_dark else "#F2F2F7"
        self.theme_btn.config(bg=P["topbar"])
        self.theme_btn._draw(self.theme_btn._normal_bg)

        # stats bar
        self.stats_bar.config(bg=P["statsbar"])
        for lbl in self.stats_labels.values():
            lbl.config(bg=P["statsbar"])

        # body
        self.body.config(bg=P["bg"])

        # sidebar
        self.sidebar.config(bg=P["sidebar"])
        self._tab_bar.config(bg=P["sidebar"])
        self._tab_divider.config(bg=P["border"])
        self.shelf_list_frame.config(bg=P["sidebar"])
        self._sidebar_action_frame.config(bg=P["sidebar"])
        for lbl in self._tab_labels.values():
            lbl.config(bg=P["sidebar"])

        # main panel
        self.main_panel.config(bg=P["bg"])
        self.filter_bar.config(bg=P["bg"])
        self.cols.config(bg=P["bg"])
        self.list_col.config(bg=P["bg"])
        self.cols_divider.config(bg=P["border"])
        self.shelf_title.config(fg=P["text"], bg=P["bg"])
        for rb in self._filter_radios:
            rb.config(bg=P["bg"], activebackground=P["bg"],
                      selectcolor=P["entry_bg"])

        self._scroll_canvas.config(bg=P["bg"])
        self.book_frame.config(bg=P["bg"])
        self.detail_panel.config(bg=P["bg"])

        # combobox style refresh
        style = ttk.Style()
        style.configure("TCombobox",
                        fieldbackground=P["entry_bg"],
                        background=P["entry_bg"],
                        foreground=P["text"],
                        selectbackground=P["card"],
                        selectforeground=P["text"])

        # redraw shelves + books (they read from PALETTE on creation)
        self.refresh_shelves()
        self.refresh_stats()
        # redraw detail panel with new palette
        if self._detail_book_id:
            self._show_detail(self._detail_book_id)
        else:
            self._show_detail_empty()

    # ── refresh ───────────────────────────────────────────────────────────────
    def refresh_shelves(self):
        """Public refresh — rebuilds whichever sidebar mode is active."""
        self._rebuild_sidebar_list()

    def refresh_books(self):
        for w in self.book_frame.winfo_children():
            w.destroy()
        search = self.search_var.get().strip()
        if self._search_has_placeholder or not search:
            search = None
        status_val   = self.status_filter.get()
        digital_only = (status_val == "digital")
        status       = None if status_val in ("all", "digital") else status_val

        if self.current_author:
            books = self.db.get_books_by_author(
                self.current_author, search=search, status=status, digital_only=digital_only)
        elif self.current_tag:
            books = self.db.get_books_by_tag(
                self.current_tag, search=search, status=status, digital_only=digital_only)
        else:
            books = self.db.get_books(
                shelf_id=self.current_shelf, search=search,
                status=status, digital_only=digital_only)
        if not books:
            tk.Label(self.book_frame, text="No books here yet.",
                     fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                     font=("Georgia", 11, "italic")).pack(pady=40)
            return
        for book in books:
            wrapper = tk.Frame(self.book_frame, bg=PALETTE["border"],
                               highlightthickness=0, bd=0)
            wrapper.pack(fill="x", padx=8, pady=2)
            card = BookCard(wrapper, book,
                            on_click=self._view_book,
                            on_edit=self._edit_book,
                            on_delete=self._delete_book,
                            on_open=self._open_book_file)
            card.pack(fill="x", padx=0, pady=0)

    def refresh_stats(self):
        s = self.db.stats()
        self.stats_labels["total"].config(text=f"📚 {s['total']} books")
        self.stats_labels["read"].config(
            text=f"✓ {s['read']} read", fg=STATUS_COLORS["read"])
        self.stats_labels["reading"].config(
            text=f"◉ {s['reading']} reading", fg=STATUS_COLORS["reading"])
        self.stats_labels["unread"].config(
            text=f"○ {s['unread']} unread", fg=STATUS_COLORS["unread"])

    def _open_book_file(self, book_id):
        b = self.db.get_book(book_id)
        if not b or not b["file_path"]:
            messagebox.showwarning("No file", "No file path is stored for this book.", parent=self)
            return
        try:
            open_file(b["file_path"])
        except FileNotFoundError as e:
            messagebox.showerror("File not found", str(e), parent=self)

    # ── add book picker ───────────────────────────────────────────────────────
    def _add_book_picker(self):
        """Show a small popup letting the user choose how to add a book."""
        picker = tk.Toplevel(self)
        picker.title("Add Book")
        picker.configure(bg=PALETTE["bg"])
        picker.resizable(False, False)
        picker.grab_set()
        picker.geometry("+%d+%d" % (self.winfo_rootx()+100, self.winfo_rooty()+110))

        f = tk.Frame(picker, bg=PALETTE["bg"], padx=28, pady=24)
        f.pack()

        tk.Label(f, text="How would you like to add a book?",
                 fg=PALETTE["text"], bg=PALETTE["bg"],
                 font=("Georgia", 12, "bold")).pack(pady=(0,18))

        btn_frame = tk.Frame(f, bg=PALETTE["bg"])
        btn_frame.pack()

        def manual():
            picker.destroy()
            BookDialog(self, self.db,
                       default_shelf_id=self.current_shelf,
                       on_save=self._on_book_saved)

        def by_isbn():
            picker.destroy()
            ISBNLookupDialog(self, self.db,
                              default_shelf_id=self.current_shelf,
                              on_save=self._on_book_saved)

        def digital():
            picker.destroy()
            DigitalImportDialog(self, self.db,
                                 default_shelf_id=self.current_shelf,
                                 on_save=self._on_book_saved)

        cards = [
            ("✏",  "Manual Entry",    "Fill in the details\nyourself",        PALETTE["border"],  manual),
            ("🔍", "Lookup by ISBN",  "Fetch details from\nOpen Library",      PALETTE["accent2"], by_isbn),
            ("📂", "Digital Import",  "Add PDF / EPUB\nfiles from disk",       STATUS_COLORS["digital"], digital),
        ]

        for icon, title, desc, border_col, cmd in cards:
            card = tk.Frame(btn_frame, bg=PALETTE["card"],
                            highlightbackground=border_col,
                            highlightthickness=1,
                            padx=16, pady=14, cursor="hand2")
            card.pack(side="left", padx=6)
            tk.Label(card, text=icon, bg=PALETTE["card"], font=("Arial", 26)).pack()
            tk.Label(card, text=title, fg=PALETTE["text"],
                     bg=PALETTE["card"], font=("Georgia", 10, "bold")).pack(pady=(4,2))
            tk.Label(card, text=desc, fg=PALETTE["text_dim"],
                     bg=PALETTE["card"], font=("Courier", 8), justify="center").pack()
            for w in [card] + list(card.winfo_children()):
                w.bind("<Button-1>", lambda e, c=cmd: c())
            card.bind("<Enter>", lambda e, c=card: c.config(bg=PALETTE["card_hover"]))
            card.bind("<Leave>", lambda e, c=card: c.config(bg=PALETTE["card"]))

        RoundedButton(f, "Cancel", command=picker.destroy,
                      width=90, height=28, bg=PALETTE["text_dim"],
                      font_size=9).pack(pady=(16,0))

    def _on_book_saved(self):
        self._rebuild_sidebar_list()   # keeps Authors list current
        self.refresh_stats()
        if self._detail_book_id:
            self._show_detail(self._detail_book_id)

    def _edit_book(self, book_id):
        BookDialog(self, self.db, book_id=book_id, on_save=self._on_book_saved)

    def _delete_book(self, book_id):
        b = self.db.get_book(book_id)
        if messagebox.askyesno("Delete", f'Delete "{b["title"]}"?', parent=self):
            self.db.delete_book(book_id)
            self._show_detail_empty()
            self._on_book_saved()

    def _view_book(self, book_id):
        self._show_detail(book_id)

    def _delete_shelf(self, shelf_id):
        if messagebox.askyesno("Delete Shelf",
                                "Delete this shelf? Books will NOT be deleted.",
                                parent=self):
            self.db.delete_shelf(shelf_id)
            if self.current_shelf == shelf_id:
                self.current_shelf = None
            self.refresh_shelves()
            self.refresh_stats()

    def _delete_tag(self, tag_id):
        if messagebox.askyesno("Delete Category",
                                "Delete this category? Books will NOT be deleted.",
                                parent=self):
            self.db.delete_tag(tag_id)
            if self.current_tag == tag_id:
                self.current_tag = None
            self.refresh_shelves()
            self.refresh_stats()

    # ── AI recs ───────────────────────────────────────────────────────────────
    def _open_recs(self):
        api_key = self.db.get_setting("anthropic_api_key",
                                       os.environ.get("ANTHROPIC_API_KEY", ""))
        RecommendDialog(self, self.db, api_key)

    # ── settings ──────────────────────────────────────────────────────────────
    def _open_settings(self):
        dlg = tk.Toplevel(self)
        dlg.title("Settings")
        dlg.configure(bg=PALETTE["bg"])
        dlg.resizable(False, False)
        dlg.grab_set()
        dlg.geometry("+%d+%d" % (self.winfo_rootx()+120, self.winfo_rooty()+100))

        f = tk.Frame(dlg, bg=PALETTE["bg"], padx=24, pady=20)
        f.pack()

        # ── theme section ──────────────────────────────────────────────────
        tk.Label(f, text="Theme", fg=PALETTE["accent"],
                 bg=PALETTE["bg"], font=("Georgia", 12, "bold")).pack(anchor="w", pady=(0,6))

        theme_row = tk.Frame(f, bg=PALETTE["bg"])
        theme_row.pack(anchor="w", pady=(0,16))
        theme_var = tk.StringVar(value=self._current_theme)

        theme_cards = {}

        def apply_theme_choice(t):
            if t == self._current_theme:
                return
            theme_var.set(t)
            self._current_theme = t
            apply_theme(t)
            self.db.set_setting("theme", t)
            self._repaint_all()
            # update card borders to reflect new selection
            for v, c in theme_cards.items():
                c.config(highlightbackground=PALETTE["accent"] if v == t else PALETTE["border"])

        for val, lbl, icon in [("dark", "Dark Mode", "🌙"), ("light", "Light Mode", "☀")]:
            is_active = (self._current_theme == val)
            border_col = PALETTE["accent"] if is_active else PALETTE["border"]
            card = tk.Frame(theme_row, bg=PALETTE["card"],
                            highlightbackground=border_col,
                            highlightthickness=2, padx=16, pady=10,
                            cursor="hand2")
            card.pack(side="left", padx=6)
            theme_cards[val] = card
            tk.Label(card, text=icon, bg=PALETTE["card"],
                     font=("Arial", 22)).pack()
            tk.Label(card, text=lbl, fg=PALETTE["text"], bg=PALETTE["card"],
                     font=("Georgia", 9, "bold")).pack()
            # mini preview swatch
            swatch_row = tk.Frame(card, bg=PALETTE["card"])
            swatch_row.pack(pady=(4,0))
            for sc in (THEMES[val]["bg"], THEMES[val]["card"], THEMES[val]["accent"]):
                tk.Label(swatch_row, bg=sc, width=2, height=1).pack(side="left", padx=1)
            tk.Radiobutton(card, variable=theme_var, value=val,
                           bg=PALETTE["card"], activebackground=PALETTE["card"],
                           selectcolor=PALETTE["entry_bg"],
                           command=lambda t=val: apply_theme_choice(t)).pack(pady=(4,0))
            card.bind("<Button-1>", lambda e, t=val: apply_theme_choice(t))
            for c in card.winfo_children():
                try:
                    c.bind("<Button-1>", lambda e, t=val: apply_theme_choice(t))
                except Exception:
                    pass

        tk.Frame(f, bg=PALETTE["border"], height=1).pack(fill="x", pady=(0,14))

        # ── API key section ────────────────────────────────────────────────
        tk.Label(f, text="Anthropic API Key", fg=PALETTE["accent"],
                 bg=PALETTE["bg"], font=("Georgia", 12, "bold")).pack(anchor="w")
        tk.Label(f, text="Used for AI book recommendations",
                 fg=PALETTE["text_dim"], bg=PALETTE["bg"],
                 font=("Courier", 8, "italic")).pack(anchor="w", pady=(0,4))
        current = self.db.get_setting("anthropic_api_key",
                                       os.environ.get("ANTHROPIC_API_KEY", ""))
        key_var = tk.StringVar(value=current)
        tk.Entry(f, textvariable=key_var, show="*",
                 bg=PALETTE["entry_bg"], fg=PALETTE["text"],
                 insertbackground=PALETTE["text"], relief="flat",
                 font=("Courier", 10), width=40).pack(pady=(0,6))
        if not ANTHROPIC_AVAILABLE:
            tk.Label(f, text="⚠ 'anthropic' package not installed. Run: pip install anthropic",
                     fg=PALETTE["accent"], bg=PALETTE["bg"],
                     font=("Courier", 8), wraplength=320).pack(pady=(0,8))

        tk.Frame(f, bg=PALETTE["border"], height=1).pack(fill="x", pady=(8,14))

        def save():
            self.db.set_setting("anthropic_api_key", key_var.get().strip())
            messagebox.showinfo("Saved", "Settings saved.", parent=dlg)
            dlg.destroy()

        btn_row = tk.Frame(f, bg=PALETTE["bg"])
        btn_row.pack()
        RoundedButton(btn_row, "Save", command=save,
                      width=100, height=30).pack(side="left", padx=4)
        RoundedButton(btn_row, "Cancel", command=dlg.destroy,
                      width=100, height=30, bg=PALETTE["text_dim"]).pack(side="left", padx=4)


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = Wiborada()
    app.mainloop()