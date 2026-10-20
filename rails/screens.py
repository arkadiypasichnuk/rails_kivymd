"""Экраны на KivyMD (бывшие Screens.py и lvls.py)."""
from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, ObjectProperty, StringProperty
from kivy.uix.widget import Widget
from kivymd.app import MDApp
from kivymd.uix.button import MDButton, MDButtonText
from kivymd.uix.card import MDCard
from kivymd.uix.dialog import (MDDialog, MDDialogButtonContainer, MDDialogHeadlineText,
                               MDDialogIcon, MDDialogSupportingText)
from kivymd.uix.screen import MDScreen

from .board import Result  # noqa: F401  (заодно регистрирует Board и Playfield для KV)
from .levels import LevelData, LevelPack
from .strings import tr


def _app():
    return MDApp.get_running_app()


class MenuScreen(MDScreen):
    def on_pre_enter(self, *args):
        _app().music.stop()  # раньше тут был вызов несуществующего sound -> NameError


class LevelCard(MDCard):
    level = ObjectProperty(None, allownone=True)
    number = NumericProperty(0)


class LevelsScreen(MDScreen):
    message = StringProperty("")  # ошибки загрузки уровней или «уровней пока нет»
    CARD, GAP = dp(88), dp(12)

    def on_kv_post(self, base_widget):
        super().on_kv_post(base_widget)
        self.ids.scroll.bind(width=self._reflow)

    def populate(self, pack: LevelPack, error: str = "") -> None:
        grid = self.ids.grid
        grid.clear_widgets()
        for level in pack.levels:
            grid.add_widget(LevelCard(level=level, number=level.id))
        problems = ([f"{tr('levels_error')}: {error}"] if error else []) + pack.errors
        self.message = "\n".join(problems) or ("" if pack.levels else tr("no_levels"))
        self._reflow()

    def _reflow(self, *_):
        """Столбцов — сколько влезает по ширине; карточки центрируются отступами."""
        grid, width = self.ids.grid, self.ids.scroll.width
        cols = max(1, int((width - 2 * self.GAP + self.GAP) // (self.CARD + self.GAP)))
        cols = min(cols, max(len(grid.children), 1))
        side = max(0.0, (width - (cols * self.CARD + (cols - 1) * self.GAP)) / 2)
        grid.cols = cols
        grid.padding = [side, self.GAP, side, self.GAP]

    def on_pre_enter(self, *args):
        _app().music.play()


class GameScreen(MDScreen):
    title = StringProperty("")
    running = BooleanProperty(False)
    level = ObjectProperty(None, allownone=True)

    def on_kv_post(self, base_widget):
        super().on_kv_post(base_widget)
        self._dialog: MDDialog | None = None
        self._refit_trigger = Clock.create_trigger(self._do_refit)
        self.ids.playfield.bind(pos=self._refit_trigger, size=self._refit_trigger)
        self.ids.board.bind(on_finish=self._on_finish, state=self._on_state)

    # ----- уровень -----
    def load_level(self, level: LevelData, announce: bool = True) -> None:
        self.level = level
        self.title = tr("level_n", n=level.id)
        self.ids.board.load(level)
        self._do_refit()
        if announce and level.hint:
            Clock.schedule_once(lambda dt: self.show_hint(), .4)

    def restart(self, *_) -> None:
        if self.level is not None:
            self._close_dialog()
            self.ids.board.load(self.level)
            self._do_refit()

    def retry(self) -> None:
        self.ids.board.stop()

    def refit(self, *_) -> None:
        """Кнопка «показать всё поле»: сбрасывает ручной зум и сдвиг."""
        self._refit_trigger()

    def _do_refit(self, *_) -> None:
        pf = self.ids.playfield
        x, y, w, h = pf.x, pf.y, pf.width, pf.height
        zone = dp(88)  # место под кнопку «Старт»
        if w >= h:
            w -= zone              # широкий экран: кнопка справа
        else:
            y, h = y + zone, h - zone  # высокий экран: кнопка снизу
        self.ids.board.fit(x, y, w, h)

    def toggle_run(self) -> None:
        board = self.ids.board
        if board.state == "running":
            board.stop()
        else:
            board.start()

    def _on_state(self, board, state) -> None:
        self.running = state == "running"

    # ----- диалоги -----
    def show_hint(self, *_) -> None:
        if self.level is not None:
            self._open_dialog("lightbulb-on-outline", tr("hint_title"),
                              self.level.hint or tr("no_hint"), [(tr("got_it"), "text", None)])

    def _on_finish(self, board, result: Result) -> None:
        app = _app()
        if result.won:
            buttons = [(tr("to_levels"), "text", app.go_levels)]
            nxt = app.next_level(self.level)
            if nxt is not None:
                buttons.append((tr("next_level"), "filled", lambda: app.open_level(nxt)))
            self._open_dialog("trophy", tr("win_title"), tr("win_text"), buttons)
        else:
            text = {"off_board": tr("lose_off_board"), "points": tr("lose_points")}.get(result.reason, tr("lose_crash"))
            self._open_dialog("alert-circle-outline", tr("lose_title"), text,
                              [(tr("to_levels"), "text", app.go_levels), (tr("retry"), "filled", self.retry)])

    def _open_dialog(self, icon: str, title: str, text: str, buttons) -> None:
        """buttons: [(подпись, стиль MDButton, обработчик или None)]"""
        self._close_dialog()

        def handler(callback):
            def on_release(*_):
                dialog.dismiss()
                if callback:
                    callback()
            return on_release

        dialog = MDDialog(
            MDDialogIcon(icon=icon),
            MDDialogHeadlineText(text=title),
            MDDialogSupportingText(text=text),
            MDDialogButtonContainer(
                Widget(),
                *[MDButton(MDButtonText(text=label), style=style, on_release=handler(cb))
                  for label, style, cb in buttons],
                spacing="8dp",
            ),
        )
        self._dialog = dialog
        dialog.open()

    def _close_dialog(self) -> None:
        if self._dialog is not None:
            self._dialog.dismiss()
            self._dialog = None

    # ----- жизненный цикл экрана -----
    def on_pre_enter(self, *args):
        _app().music.play()

    def on_leave(self, *args):
        self._close_dialog()
        self.ids.board.stop()  # раньше уход с экрана посреди поездки навсегда блокировал игру
