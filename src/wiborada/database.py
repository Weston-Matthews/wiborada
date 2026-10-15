"""SQLite database layer for Wiborada personal library manager."""

import os
import sqlite3

DB_PATH = os.path.join(os.path.expanduser("~"), ".personal_library.db")

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
        # Indexes for common query patterns
        self.conn.executescript("""
            CREATE INDEX IF NOT EXISTS idx_books_status  ON books(status);
            CREATE INDEX IF NOT EXISTS idx_books_author  ON books(author);
            CREATE INDEX IF NOT EXISTS idx_books_title   ON books(title);
            CREATE INDEX IF NOT EXISTS idx_books_digital ON books(is_digital);
            CREATE INDEX IF NOT EXISTS idx_book_shelves_shelf ON book_shelves(shelf_id);
            CREATE INDEX IF NOT EXISTS idx_book_tags_tag      ON book_tags(tag_id);
        """)
        # WAL mode: faster concurrent reads, no full-table locks on write
        self.conn.executescript("""
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=NORMAL;
            PRAGMA cache_size=-8000;
            PRAGMA temp_store=MEMORY;
        """)
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
