"""Фоновая музыка: один плеер на всё приложение (раньше у каждого экрана был свой)."""
from __future__ import annotations

import os

from kivy.core.audio import SoundLoader
from kivy.logger import Logger


class MusicPlayer:
    def __init__(self, source: str):
        self.source = source
        self.enabled = True
        self._wanted = False   # хотим ли, чтобы сейчас играла музыка
        self._loaded = False
        self._sound = None

    def _load(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        if not os.path.exists(self.source):
            Logger.warning(f"Music: файл не найден — {self.source}")
            return
        try:
            self._sound = SoundLoader.load(self.source)
        except Exception as e:  # у некоторых платформ загрузчик может упасть
            Logger.warning(f"Music: не удалось загрузить звук — {e}")
        if self._sound:
            self._sound.loop = True

    def _sync(self) -> None:
        if self._wanted and self.enabled:
            self._load()
            if self._sound and self._sound.state != "play":
                self._sound.play()
        elif self._sound and self._sound.state == "play":
            self._sound.stop()

    def play(self) -> None:
        self._wanted = True
        self._sync()

    def stop(self) -> None:
        self._wanted = False
        self._sync()

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        self._sync()
        return self.enabled

    def pause(self) -> None:  # приложение свернули (Android)
        if self._sound and self._sound.state == "play":
            self._sound.stop()

    def resume(self) -> None:
        self._sync()
