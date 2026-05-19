"""Замена школьной терминологии на нейтральную в ru/en.json (значения ключей)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCALES = ROOT / "static" / "locales"

# Порядок важен: длинные фразы раньше коротких.
RU_REPLACEMENTS: list[tuple[str, str]] = [
    ("Следующий учебный день:", "Следующий рабочий день:"),
    ("Уроки и Excel", "Расписание и Excel"),
    ("Новости школы", "Новости"),
    ("Расписание уроков", "Расписание"),
    ("звонков по расписанию", "сигналов по расписанию"),
    ("звонков из админки", "сигналов из админки"),
    ("файлов звонков", "файлов сигналов"),
    ("файл звонка", "файл сигнала"),
    ("Звуки звонков", "Звуки сигналов"),
    ("шаблонов звонков", "шаблонов сигналов"),
    ("Шаблон звонков", "Шаблон сигналов"),
    ("расписания звонков", "расписания сигналов"),
    ("расписание звонков", "расписание сигналов"),
    ("Звонки по расписанию", "Сигналы по расписанию"),
    ("Сохранить звонки", "Сохранить сигналы"),
    ("Звонки сохранены", "Сигналы сохранены"),
    ("Последний урок дня", "Последний слот дня"),
    ("последний урок", "последний слот"),
    ("начало/конец урока", "начало/конец слота"),
    ("конец урока", "конец слота"),
    ("начало урока", "начало слота"),
    ("до урока", "до слота"),
    ("До звонка", "До сигнала"),
    ("«Урок»", "«Слот»"),
    ("Урок или название", "Слот или название"),
    ("Название урока", "Название записи"),
    ("номера урока", "номера слота"),
    ("на уроке", "в слоте"),
    ("сейчас урок", "сейчас слот"),
    ("первого урока", "первого слота"),
    ("следующего» в последнюю минуту до урока", "следующего» в последнюю минуту до слота"),
    ("Приоритет на уроке", "Приоритет на слоте"),
    ("уроки по номерам", "слоты по номерам"),
    ("уроки.", "слоты."),
    ("уроки,", "слоты,"),
    ("уроки ", "слоты "),
    ("уроков)", "слотов)"),
    (" уроков", " слотов"),
    (" урок ", " слот "),
    ("| урок ", "| слот "),
    ("Уроки и звонки", "Расписание и сигналы"),
    ("Урок", "Слот"),
    ("урок", "слот"),
    ("Звонки", "Сигналы"),
    ("звонки", "сигналы"),
    ("звонок", "сигнал"),
    ("Звонок", "Сигнал"),
    ("Класс", "Группа"),
    ("класс", "группа"),
    ("классы", "группы"),
    ("параллели", "подгруппы"),
    ("младших классов", "младших групп"),
    ("старших", "старших"),  # noop anchor
    ("старших ~", "старших ~"),
    ("Регистрация школ", "Регистрация организации"),
    ("часовому поясу школы", "часовому поясу организации"),
    ("КОД ШКОЛЫ", "КОД ПОДКЛЮЧЕНИЯ"),
]

EN_REPLACEMENTS: list[tuple[str, str]] = [
    ("Next school day:", "Next schedule day:"),
    ("Lessons & Excel", "Schedule & Excel"),
    ("School news", "News"),
    ("lesson schedule", "schedule"),
    ("Lessons & bells", "Schedule & signals"),
    ("bell schedule", "signal schedule"),
    ("Bell template", "Signal template"),
    ("Bell schedule", "Signal schedule"),
    ("Scheduled bells", "Scheduled signals"),
    ("Save bells", "Save signals"),
    ("Bells saved", "Signals saved"),
    ("Last lesson of day", "Last slot of day"),
    ("last lesson", "last slot"),
    ("lesson start/end", "slot start/end"),
    ("end of lesson", "end of slot"),
    ("class start", "slot start"),
    ("before class", "before slot"),
    ("class now", "active slot"),
    ("first lesson", "first slot"),
    ("next lesson", "next slot"),
    ("Per lesson", "Per slot"),
    ("numbered lessons", "numbered slots"),
    ("lessons.", "slots."),
    ("lessons,", "slots,"),
    ("lessons ", "slots "),
    (" lessons)", " slots)"),
    (" lessons", " slots"),
    (" lesson ", " slot "),
    ("| lesson ", "| slot "),
    ("Lesson title", "Entry title"),
    ("Lesson field", "Slot field"),
    ("Lesson or label", "Slot or label"),
    ("Lesson", "Slot"),
    ("lesson", "slot"),
    ("Bells", "Signals"),
    ("bells", "signals"),
    ("bell", "signal"),
    ("Bell", "Signal"),
    ("Class", "Group"),
    ("class", "group"),
    ("classes", "groups"),
    ("school", "organization"),
    ("School", "Organization"),
]


_PROTECT = [
    ("GuardSchool", "\x00GS\x00"),
    ("guardschool", "\x00gs\x00"),
    ("GUARDSCHOOL", "\x00GSS\x00"),
]


def apply_replacements(text: str, pairs: list[tuple[str, str]]) -> str:
    out = text
    for old, ph in _PROTECT:
        out = out.replace(old, ph)
    for old, new in pairs:
        out = out.replace(old, new)
    for old, ph in _PROTECT:
        out = out.replace(ph, old)
    return out


def walk(obj: object, pairs: list[tuple[str, str]]) -> object:
    if isinstance(obj, str):
        return apply_replacements(obj, pairs)
    if isinstance(obj, list):
        return [walk(x, pairs) for x in obj]
    if isinstance(obj, dict):
        return {k: walk(v, pairs) for k, v in obj.items()}
    return obj


def main() -> None:
    for name, pairs in (("ru.json", RU_REPLACEMENTS), ("en.json", EN_REPLACEMENTS)):
        path = LOCALES / name
        data = json.loads(path.read_text(encoding="utf-8"))
        data2 = walk(data, pairs)
        path.write_text(json.dumps(data2, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("updated", path.name)
    # verify key parity
    ru = json.loads((LOCALES / "ru.json").read_text(encoding="utf-8"))
    en = json.loads((LOCALES / "en.json").read_text(encoding="utf-8"))
    assert set(ru) == set(en), f"key mismatch ru-only={set(ru)-set(en)} en-only={set(en)-set(ru)}"
    print("keys ok", len(ru))


if __name__ == "__main__":
    main()
