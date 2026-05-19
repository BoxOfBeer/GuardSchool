# TV widget render plugins (JS)

Порядок на ТВ (см. `screen.html`, `app.js`):

1. `runtime.js` — `GuardSchoolWidgets.register(type, fn)`
2. `carousel-runtime.js` — состояние и таймеры карусели (`GuardSchoolWidgets.carousel`)
3. `screen_widgets.js` — ядро, `helpers`, fallback для типов без плагина
4. `{type}.js` — рендер одного типа (после ядра)

Вынесено (все типы с `renderWidgetHtmlImpl`): `date`, `time`, `text`, `blank`, `emergency`, `image`, `bell_status`, `bell_countdown`, `holidays`, `schedule`, `announcements`, `marquee`, `school_news`, `rss_news`, `checkin_submit`, `checkin_monitor`.

`carousel` — `carousel-runtime.js` + `GuardSchoolScreen.startCarousel` в `screen.js` / превью; дочерние виджеты рендерятся через `renderWidgetHtml`, не как отдельный JS-плагин.

Ядро `screen_widgets.js` держит `helpers` (build*, state бегущей строки) и runtime API `GuardSchoolScreen`; state карусели — в `GuardSchoolWidgets.carousel`.

Плагин возвращает HTML-строку; `undefined` — делегировать в ядро.

```javascript
GuardSchoolWidgets.register("my_type", function (ctx) {
  const w = ctx.widget;
  const weight = ctx.weight || "";
  return "<span class=\"widget-center-text\">…</span>";
});
```

`ctx`: `widget`, `schedule`, `screen`, `holidays`, `announcements`, `marquee`, `schoolNews`, `rssNews`, `ctx`, `weight`, `L`, `wtype`.
