"""Wiborada — Personal Library Manager

Thin entry point. Run with: python main.py
"""

from src.wiborada.app import LibraryApp

if __name__ == "__main__":
    app = LibraryApp()
    app.mainloop()
