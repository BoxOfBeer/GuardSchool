"""Сервер GuardSchool: FastAPI, данные, воркеры звука.

Не импортируйте сюда `app` (экземпляр FastAPI): имя `app` в пакете перекрыло бы
подмодуль `guardschool.app`, и выражение ``from . import app`` в соседних модулях
(например local_audio_worker) получало бы не модуль с load_config, а приложение.
Используйте: ``from guardschool.app import app``.
"""
