"""Спрайт поезда и его анимация (бывший Train.py без логики уровня)."""
from __future__ import annotations

from kivy.animation import Animation
from kivy.graphics import PopMatrix, PushMatrix, Rotate
from kivy.properties import NumericProperty
from kivy.uix.image import Image

from .paths import asset
from .pieces import CELL

TRAIN_W, TRAIN_H = CELL * 1.8, CELL * 1.6  # те же размеры, что были у SizeTrainx/SizeTrainy
TRAIN_LEN = TRAIN_H                        # длина вдоль движения


def shortest_angle(current: float, target: float) -> float:
    """Угол, эквивалентный target, до которого от current ближе всего."""
    return current + (target - current + 180) % 360 - 180


class Train(Image):
    angle = NumericProperty(0)

    def __init__(self, **kwargs):
        super().__init__(source=asset("train.png"), size_hint=(None, None),
                         size=(TRAIN_W, TRAIN_H), **kwargs)
        with self.canvas.before:
            PushMatrix()
            self._rot = Rotate(angle=0, origin=self.center)
        with self.canvas.after:
            PopMatrix()
        self.bind(pos=self._sync_origin, size=self._sync_origin, angle=self._sync_angle)

    def _sync_origin(self, *_):
        # считаем центр руками: у кэшируемого свойства center бывает устаревшая y в момент события pos
        self._rot.origin = (self.x + self.width / 2, self.y + self.height / 2)

    def _sync_angle(self, *_):
        self._rot.angle = self.angle

    def place(self, center: tuple[float, float], angle: float) -> None:
        """Мгновенно поставить поезд (центр спрайта в center)."""
        Animation.cancel_all(self)
        self.center = center
        self.angle = shortest_angle(self.angle, angle)

    def go(self, center: tuple[float, float], angle: float, duration: float, on_done=None) -> None:
        """Плавно переехать в center, повернувшись кратчайшим путём."""
        Animation.cancel_all(self)
        anim = Animation(pos=(center[0] - self.width / 2, center[1] - self.height / 2),
                         angle=shortest_angle(self.angle, angle), d=duration, t="linear")
        if on_done:
            anim.bind(on_complete=lambda *_: on_done())
        anim.start(self)
