/**
 * Подписи виджетов на ТВ (ru/en) — синхронизировать с static/locales/*.json (tv.*).
 */
(function (global) {
  const TV_UI = {
    ru: {
      noData: "Нет данных",
      lessonColumn: "Слот",
      bells: "Сигналы",
      countdown: "До сигнала",
      events: "События",
      announcements: "Объявления",
      schoolNews: "Новости",
      rssNews: "RSS-лента",
      noAnnouncements: "Нет объявлений",
      noSchoolNews: "Нет новостей",
      qr: "QR на материал",
      noRssNews: "Нет новостей",
      scheduleDefault: "Расписание",
      nextSchoolDay: "Следующий рабочий день:",
      carouselBlank: "Пауза (фон)",
      imageEmpty: "Нет изображения (добавьте файл или URL)",
      imageAlt: "изображение",
      carouselNoSlides: "Слайды не выбраны",
      emergencyTimeLeft: "Осталось времени:",
      widgetMissing: "Виджет {{type}} отсутствует.",
      widgetError: "Ошибка виджета {{type}}.",
    },
    en: {
      noData: "No data",
      lessonColumn: "Slot",
      bells: "Signals",
      countdown: "Until signal",
      events: "Events",
      announcements: "Announcements",
      schoolNews: "News",
      rssNews: "RSS feed",
      noAnnouncements: "No announcements",
      noSchoolNews: "No news",
      qr: "QR to article",
      noRssNews: "No news",
      scheduleDefault: "Schedule",
      nextSchoolDay: "Next schedule day:",
      carouselBlank: "Pause (background)",
      imageEmpty: "No image (add a file or URL)",
      imageAlt: "image",
      carouselNoSlides: "No slides selected",
      emergencyTimeLeft: "Time left:",
      widgetMissing: "Widget {{type}} is missing.",
      widgetError: "Widget {{type}} error.",
    },
  };
  global.GuardSchoolTvLocales = TV_UI;
})(typeof window !== "undefined" ? window : globalThis);
