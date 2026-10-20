"""Точка входа:  python main.py   (нужен Python 3.11+ из-за tomllib).

Другой файл уровней:  RAILS_LEVELS=suns/test.toml python main.py
"""
import os

# Отладка на ПК, как и в старом Main.py: если задан KIVY_GL_BACKEND — окно 1000×1000.
if "KIVY_GL_BACKEND" in os.environ:
    from kivy.core.window import Window
    Window.size = (1000, 1000)
    del os.environ["KIVY_GL_BACKEND"]

from rails.app import RailsApp  # noqa: E402

if __name__ == "__main__":
    RailsApp(levels_path=os.environ.get("RAILS_LEVELS")).run()
