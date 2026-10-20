"""Все тексты интерфейса в одном месте. Язык меняется константой LANG."""
LANG = "uk"  # "uk" | "ru" | "en"

_TEXTS = {
    "uk": {
        "app_title": "Рейки", "play": "Грати", "exit": "Вийти", "levels": "Рівні",
        "level_n": "Рівень {n}", "start": "Старт", "stop": "Стоп",
        "hint_title": "Підказка", "got_it": "Зрозуміло", "no_hint": "Для цього рівня підказки немає.",
        "fit_view": "Показати все поле", "restart": "Почати рівень заново",
        "win_title": "Перемога!", "win_text": "Поїзд доїхав до кінця.",
        "lose_title": "Поразка",
        "lose_crash": "Поїзд зійшов з рейок: на його шляху немає колії або вона не з’єднана.",
        "lose_off_board": "Поїзд виїхав за межі поля.",
        "lose_points": "Поїзд доїхав до кінця, але не через усі позначені станції.",
        "next_level": "Далі", "retry": "Ще раз", "to_levels": "До рівнів",
        "levels_error": "Не вдалося завантажити рівні", "no_levels": "Рівнів поки немає",
    },
    "ru": {
        "app_title": "Рельсы", "play": "Играть", "exit": "Выйти", "levels": "Уровни",
        "level_n": "Уровень {n}", "start": "Старт", "stop": "Стоп",
        "hint_title": "Подсказка", "got_it": "Понятно", "no_hint": "Для этого уровня подсказки нет.",
        "fit_view": "Показать всё поле", "restart": "Начать уровень заново",
        "win_title": "Победа!", "win_text": "Поезд доехал до конца.",
        "lose_title": "Поражение",
        "lose_crash": "Поезд сошёл с рельс: на его пути нет колеи или она не соединена.",
        "lose_off_board": "Поезд выехал за пределы поля.",
        "lose_points": "Поезд доехал до конца, но не через все отмеченные станции.",
        "next_level": "Дальше", "retry": "Ещё раз", "to_levels": "К уровням",
        "levels_error": "Не удалось загрузить уровни", "no_levels": "Уровней пока нет",
    },
    "en": {
        "app_title": "Rails", "play": "Play", "exit": "Exit", "levels": "Levels",
        "level_n": "Level {n}", "start": "Start", "stop": "Stop",
        "hint_title": "Hint", "got_it": "Got it", "no_hint": "No hint for this level.",
        "fit_view": "Fit the whole field", "restart": "Restart level",
        "win_title": "You win!", "win_text": "The train reached the end.",
        "lose_title": "You lose",
        "lose_crash": "The train derailed: there is no connected track on its way.",
        "lose_off_board": "The train left the field.",
        "lose_points": "The train arrived, but not through all marked stations.",
        "next_level": "Next", "retry": "Retry", "to_levels": "Levels",
        "levels_error": "Could not load levels", "no_levels": "No levels yet",
    },
}


def tr(key: str, **fmt) -> str:
    text = _TEXTS.get(LANG, _TEXTS["en"]).get(key) or _TEXTS["en"].get(key) or key
    return text.format(**fmt) if fmt else text
