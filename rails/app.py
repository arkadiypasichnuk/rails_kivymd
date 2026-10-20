"""Приложение: тема, навигация между экранами, уровни, музыка (бывший Main.py)."""
from __future__ import annotations

from pathlib import Path

from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import StringProperty
from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager

from . import strings
from .audio import MusicPlayer
from .levels import LevelData, LevelError, LevelPack, load_pack
from .paths import DEFAULT_LEVELS, KV_DIR, asset
from .screens import GameScreen, LevelsScreen, MenuScreen


class RailsApp(MDApp):
    music_icon = StringProperty("volume-high")

    def __init__(self, levels_path: str | Path | None = None, **kwargs):
        super().__init__(**kwargs)
        self.levels_path = Path(levels_path) if levels_path else DEFAULT_LEVELS
        self.pack = LevelPack("", [], [])
        self.load_error = ""
        self.music = MusicPlayer(asset("Music", "fon_game.mp3"))

    def tr(self, key: str, **fmt) -> str:
        """Текст интерфейса для KV:  text: app.tr("play")"""
        return strings.tr(key, **fmt)

    def build(self):
        self.title = self.tr("app_title")
        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "Blue"
        for name in ("board.kv", "screens.kv"):
            Builder.load_file(str(KV_DIR / name))

        try:
            self.pack = load_pack(self.levels_path)
        except LevelError as e:  # битый файл не должен ронять приложение
            self.load_error = str(e)

        sm = MDScreenManager()
        sm.add_widget(MenuScreen(name="menu"))
        levels = LevelsScreen(name="levels")
        levels.populate(self.pack, self.load_error)
        sm.add_widget(levels)
        sm.add_widget(GameScreen(name="game"))
        Window.bind(on_keyboard=self._on_keyboard)
        return sm

    # ----- навигация -----
    def _go(self, screen: str, direction: str) -> None:
        self.root.transition.direction = direction
        self.root.current = screen

    def go_menu(self) -> None:
        self._go("menu", "right")

    def go_levels(self) -> None:
        self._go("levels", "right" if self.root.current == "game" else "left")

    def open_level(self, level: LevelData) -> None:
        self.root.get_screen("game").load_level(level)
        self._go("game", "left")

    def next_level(self, level: LevelData | None) -> LevelData | None:
        levels = self.pack.levels
        if level in levels and levels.index(level) + 1 < len(levels):
            return levels[levels.index(level) + 1]
        return None

    def _on_keyboard(self, window, key, *args) -> bool:
        """Кнопка «назад» на Android / Esc на ПК: игра -> уровни -> меню."""
        if key == 27:
            if self.root.current == "game":
                self.go_levels()
                return True
            if self.root.current == "levels":
                self.go_menu()
                return True
        return False  # в меню — стандартное поведение (выход)

    # ----- настройки -----
    def toggle_music(self) -> None:
        self.music_icon = "volume-high" if self.music.toggle() else "volume-off"

    def toggle_theme(self) -> None:
        self.theme_cls.switch_theme()

    # ----- жизненный цикл -----
    def on_pause(self) -> bool:
        self.music.pause()
        return True

    def on_resume(self) -> None:
        self.music.resume()

    def on_stop(self) -> None:
        self.music.stop()
