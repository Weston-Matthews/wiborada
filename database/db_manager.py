"""
Database Manager - Handles all the SQLite database functions
"""

import sqlite3
from datetime import datetime
import os


class DatabaseManager:
    # Manages SQLite database connections and operations
    
    def __init__(self, db_path='library.db'):
        # Initialize database connection and build tables if needed
        self.db_path = db_path;
        self.conn = sqlite3.connect(db_path);
        self.conn.row_factory = sqlite3.Row; # Return rows as dictionaries
        self.cursor = self.conn.cursor();
        self._create_tables();
    
    def _create_tables(self):
        # Create database tables if they don't exist
        
        # Create shelves table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS shelves (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                color TEXT DEFAULT '#4A90D9',
                created_at TEXT DEFAULT (datetime('now'))
            )
        ''');
        
        # Create book table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                author TEXT,
                genre TEXT,
                year INTEGER,
                rating INTEGER CHECK(rating BETWEEN 1 AND 5),
                status TEXT DEFAULT 'unread',
                notes TEXT,
                cover_color TEXT DEFAULT '#2C3E50',
                isbn TEXT,
                cover_image TEXT,
                added TEXT DEFAULT (datetime('now'))
            )
        ''');
        
        # Create book_shelves table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS book_shelves (
                book_id INTEGER REFERENCES books(id) ON DELETE CASCADE,
                shelf_id INTEGER REFERENCES shelves(id) ON DELETE CASCADE,
                PRIMARY KEY (book_id, shelf_id)
            )
        ''');
        
        # Create the settings table
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''');
        
        self.conn.commit();
    
    # -- Shelf functions
    
    def get_shelves(self):
        return self.conn.execute("SELECT * FROM shelves ORDER BY name").fetchall()
    
    def add_shelf(self, name, color='#4A90D9'):
        self.conn.execute("INSERT INTO shelves (name, color) VALUES (?,?)", (name, color));
        self.conn.commit();
    
    def rename_shelf(self, shelf_id, new_name):
        self.conn.execute("UPDATE shelves SET name=? WHERE id=?", (new_name, shelf_id));
        self.conn.commit();
    
    def delete_shelf(self, shelf_id):
        self.conn.execute("DELETE FROM shelves WHERE id=?", (shelf_id));
        self.conn.commit();
    
    def update_shelf_color(self, shelf_id, color):
        self.conn.execute("UPDATE shelves SET color=? WHERE id=?", (color, shelf_id));
        self.conn.commit();
    
    # -- Book functions
    
    def get_books(self, shelf_id=None, search=None, status=None):
        q = "SELECT b.* FROM books b";
        params = [];
        if shelf_id:
            q += " JOIN book_shelves bs ON b.id=bs.book_id WHERE bs.shelf_id=?";
            params.append(shelf_id);
            if search:
                q += " AND (b.title LIKE ? OR b.author LIKE ?)";
                params += [f"%{search}%", f"%{search}%"];
            if status:
                q += " AND b.status=?";
                params.append(status);
        else:
            clauses = [];
            if search:
                clauses.append("(title LIKE ? OR author LIKE ?)");
                params += [f"%{search}%", f"%{search}%"];
            if status:
                clauses.append("status=?");
                params.append(status);
            if clauses:
                q += " WHERE " + " AND ".join(clauses);
        q += " ORDER BY b.title";
        return self.conn.execute(q, params).fetchall()
    
    def get_book(self, book_id):
        return self.conn.execute("SELECT * FROM books WHERE id=?", (book_id)).fetchone()
    
    def add_book(self, title, author, genre, year, rating, status='unread', notes='', cover_color='#2C3E50', isbn='', cover_image=''):
        new_book = self.conn.execute(
            "INSERT INTO books (title, author, genre, year, rating, status, notes, cover_color, isbn, cover_image) VALUES (?,?,?,?,?,?,?,?)",
            (title, author, genre, year, rating, status, notes, cover_color, isbn, cover_image)
        );
        self.conn.commit();
        return new_book.lastrowid
    
    def update_book(self, book_id, title, author, genre, year, rating, status, notes, cover_color, isbn, cover_image):
        self.conn.execute(
            "UPDATE books SET title=?,author=?,genre=?,year=?,rating=?,status=?,notes=?,cover_color=?,isbn=?,cover_image=? WHERE id=?",
            (title, author, genre, year, rating, status, notes, cover_color, isbn, cover_image, book_id)
        )
        self.conn.commit();
    
    def delete_book(self, book_id):
        self.conn.execute("DELETE FROM books WHERE book_id=?", (book_id));
        self.conn.commit();
    
    def get_book_shelves(self, book_id):
        return self.conn.execute(
            "SELECT s.* FROM shelves s JOIN book_shelves bs ON s.id=bs.shelf_id WHERE bs.book_id=?",
            (book_id,)
        ).fetchall()
    
    def assign_book_to_shelf(self, book_id, shelf_id):
        self.conn.execute(
            "INSERT OR IGNORE INTO book_shelves (book_id, shelf_id) VALUES (?,?)", (book_id, shelf_id)
        );
        self.conn.commit();
    
    def remove_book_from_shelf(self, book_id, shelf_id):
        self.conn.execute(
            "DELETE FROM book_shelves WHERE book_id=? AND shelf_id=?", (book_id, shelf_id)
        );
        self.conn.commit();
    
    # -- Settings functions
    
    def get_setting(self, key, default=None):
        row = self.conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone();
        return row["value"] if row else default

    def set_setting(self, key, value):
        self.conn.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (key, value));
        self.conn.commit();
    
    # -- Stats
    
    def stats(self):
        total   = self.conn.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        read    = self.conn.execute("SELECT COUNT(*) FROM books WHERE status='read'").fetchone()[0]
        reading = self.conn.execute("SELECT COUNT(*) FROM books WHERE status='reading'").fetchone()[0]
        unread  = self.conn.execute("SELECT COUNT(*) FROM books WHERE status='unread'").fetchone()[0]
        shelves = self.conn.execute("SELECT COUNT(*) FROM shelves").fetchone()[0]
        return {"total": total, "read": read, "reading": reading, "unread": unread, "shelves": shelves}

    def get_all_books_summary(self):
        """Return a compact text summary of all books for AI context."""
        rows = self.conn.execute(
            "SELECT title, author, genre, status, rating FROM books ORDER BY title"
        ).fetchall()
        lines = []
        for r in rows:
            rating_str = f", rated {r['rating']}/5" if r['rating'] else ""
            lines.append(f"- {r['title']} by {r['author'] or 'Unknown'}"
                         f" ({r['genre'] or 'no genre'}, {r['status']}{rating_str})")
        return "\n".join(lines) if lines else "No books in library yet."