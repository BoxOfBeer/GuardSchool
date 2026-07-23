(function (global) {
  "use strict";
  const W = global.GuardSchoolWidgets;
  if (!W) return;
  const H = W.helpers || {};
  const esc = H.escapeHtml || ((s) => String(s == null ? "" : s).replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])));
  const apiFetch = (url, init) => (global.gsCheckinApiFetch || global.fetch)(url, Object.assign({credentials:"include"}, init || {}));
  const weekday = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"];
  const statuses = {confirmed:"Подтверждена",cancel_requested:"Ожидает решения",cancelled:"Отменена",completed:"Завершена",no_show:"Не состоялась"};
  const labelNames = {title:"Заголовок",resource:"Название ресурса",place:"Название места",service:"Название услуги",person:"Название посетителя",family_name:"Поле фамилии",given_name:"Поле имени",phone:"Поле телефона"};
  const defaultPublicColors = {action:"#2563eb",text:"#ffffff",free:"#16a34a",booked:"#b91c1c",cancel:"#ca8a04"};

  function validColor(value, fallback) {
    const color=String(value||"").trim().toLowerCase();
    return /^#[0-9a-f]{6}$/.test(color)?color:fallback;
  }

  function publicColors(ctx, settings) {
    const moduleId=String(settings.module_id||"booking-main");
    const widgets=ctx&&ctx.screen&&Array.isArray(ctx.screen.widgets)?ctx.screen.widgets:[];
    const manager=widgets.find((item)=>item&&item.type==="booking_manager"&&String(item.settings&&item.settings.module_id||"booking-main")===moduleId);
    const source=manager&&manager.settings&&typeof manager.settings==="object"?manager.settings:settings;
    return {
      action:validColor(source.public_action_color,defaultPublicColors.action),
      text:validColor(source.public_action_text_color,defaultPublicColors.text),
      free:validColor(source.public_free_color,defaultPublicColors.free),
      booked:validColor(source.public_booked_color,defaultPublicColors.booked),
      cancel:validColor(source.public_cancel_color,defaultPublicColors.cancel),
    };
  }

  function managerColors(settings, fallback) {
    return {
      action:validColor(settings.manager_action_color,fallback.action),
      text:validColor(settings.manager_action_text_color,fallback.text),
    };
  }

  function shell(ctx, kind) {
    const s = ctx.widget.settings || {};
    const title = s.heading || (kind === "public" ? "Запись" : "Управление записями");
    const colors=publicColors(ctx,s),actions=kind==="manager"?managerColors(s,colors):colors;
    const colorStyle=`--bk-action-bg:${actions.action};--bk-button-text:${actions.text};--bk-free-bg:${colors.free};--bk-booked-bg:${colors.booked};--bk-cancel-bg:${colors.cancel}`;
    return `<div class="gs-booking" data-booking-kind="${kind}" data-module-id="${esc(s.module_id || "booking-main")}" style="${colorStyle}">
      <style>.gs-booking{box-sizing:border-box;height:100%;overflow:auto;padding:14px;color:inherit;font:inherit}.gs-booking *{box-sizing:border-box}.gs-booking h2{margin:0 0 10px;font-size:1.18em}.gs-booking button,.gs-booking input,.gs-booking select,.gs-booking textarea{font:inherit;border:1px solid rgba(148,163,184,.55);border-radius:8px;padding:8px 10px}.gs-booking input,.gs-booking select,.gs-booking textarea{color:#0f172a!important;background:#fff!important;text-shadow:none!important;-webkit-text-stroke:0 transparent!important}.gs-booking input::placeholder,.gs-booking textarea::placeholder{color:#64748b!important;opacity:1;text-shadow:none!important;-webkit-text-stroke:0 transparent!important}.gs-booking button{cursor:pointer;background:var(--bk-action-bg);color:var(--bk-button-text)}.gs-booking button[disabled]{cursor:default}.gs-booking .bk-muted{opacity:.75;font-size:.88em}.gs-booking .bk-error{color:#fecaca;background:rgba(127,29,29,.55);padding:8px;border-radius:8px}.gs-booking .bk-toolbar{display:flex;gap:7px;align-items:center;flex-wrap:wrap;margin-bottom:10px}.gs-booking .bk-filter{display:flex;grid-template-columns:auto 1fr;align-items:center;gap:6px;padding:5px 8px;border:1px solid rgba(148,163,184,.45);border-radius:8px}.gs-booking .bk-filter input{width:auto;margin:0;padding:0}.gs-booking .bk-days{display:block}.gs-booking .bk-day{width:100%;background:rgba(15,23,42,.38);padding:9px;border-radius:9px}.gs-booking .bk-day strong{display:block;margin-bottom:6px}.gs-booking .bk-slot{display:block;width:100%;margin:4px 0;padding:8px}.gs-booking .bk-slot--free{background:var(--bk-free-bg)}.gs-booking .bk-slot--free.is-selected{box-shadow:0 0 0 3px rgba(255,255,255,.8) inset}.gs-booking .bk-slot--booked{background:var(--bk-booked-bg);opacity:1}.gs-booking .bk-slot--cancel{background:var(--bk-cancel-bg);opacity:1}.gs-booking .bk-legend{display:flex;gap:12px;flex-wrap:wrap;margin:7px 2px 2px;font-size:.76em;opacity:.9}.gs-booking .bk-legend span{display:flex;align-items:center;gap:5px}.gs-booking .bk-dot{width:9px;height:9px;border-radius:50%;display:inline-block}.gs-booking .bk-form{display:grid;grid-template-columns:repeat(4,minmax(110px,1fr));gap:7px;margin:10px 0}.gs-booking .bk-list{display:grid;gap:7px}.gs-booking .bk-card{padding:9px;border:1px solid rgba(148,163,184,.35);border-radius:9px;background:rgba(15,23,42,.3)}.gs-booking .bk-grid{display:grid;grid-template-columns:repeat(2,minmax(180px,1fr));gap:8px}.gs-booking label{display:grid;gap:4px}.gs-booking textarea{min-height:90px}.gs-booking details{margin-top:10px}.gs-booking table{width:100%;border-collapse:collapse}.gs-booking td,.gs-booking th{padding:6px;border-bottom:1px solid rgba(148,163,184,.3);text-align:left}.gs-booking .bk-actions{display:flex;gap:5px;flex-wrap:wrap}.gs-booking tr.bk-row--cancel-requested td{background:rgba(202,138,4,.32);border-top:1px solid #facc15;border-bottom:1px solid #facc15}.gs-booking tr.bk-row--hidden{display:none}.gs-booking .bk-move-row td{padding:10px;background:rgba(15,23,42,.2)}.gs-booking .bk-move-form{display:grid;gap:9px}.gs-booking .bk-move-fields{display:grid;grid-template-columns:minmax(150px,1fr) repeat(2,minmax(90px,.45fr));gap:8px}.gs-booking .bk-move-actions{display:flex;gap:7px;flex-wrap:wrap;align-items:center}@media(max-width:700px){.gs-booking .bk-form,.gs-booking .bk-grid,.gs-booking .bk-move-fields{grid-template-columns:1fr}}</style>
      <h2>${esc(title)}</h2><div class="bk-body"><div class="bk-muted">Загрузка…</div></div></div>`;
  }
  W.register("booking_public", (ctx) => shell(ctx, "public"));
  W.register("booking_manager", (ctx) => shell(ctx, "manager"));

  function deviceId(moduleId) {
    const key = `gs_booking_device_${moduleId}`;
    try {
      let id = localStorage.getItem(key);
      if (!id) { id = global.crypto && crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}-${Math.random()}`; localStorage.setItem(key, id); }
      return id;
    } catch (_) { return `session-${Date.now()}-${Math.random()}`; }
  }
  function weekIso(delta) { const d=new Date();d.setHours(12,0,0,0);d.setDate(d.getDate()-((d.getDay()+6)%7)+delta*7);return d.toISOString().slice(0,10); }
  function addIsoDays(iso, delta) { const d=new Date(`${iso}T12:00:00Z`);d.setUTCDate(d.getUTCDate()+delta);return d.toISOString().slice(0,10); }
  function mondayIsoForDate(iso) { const d=new Date(`${iso}T12:00:00Z`);d.setUTCDate(d.getUTCDate()-((d.getUTCDay()+6)%7));return d.toISOString().slice(0,10); }
  function dayTitle(iso) { const d=new Date(`${iso}T12:00:00Z`);return new Intl.DateTimeFormat("ru-RU",{weekday:"long",day:"2-digit",month:"2-digit"}).format(d); }
  async function json(url, init) { const r=await apiFetch(url,init);let b={};try{b=await r.json()}catch(_){}if(!r.ok)throw new Error(b.detail||`Ошибка ${r.status}`);return b; }
  function fmt(iso, timeZone) { const options={day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"};if(timeZone)options.timeZone=timeZone;return new Intl.DateTimeFormat("ru-RU",options).format(new Date(iso)); }
  function zonedDateTimeParts(iso, timeZone) {
    const value=new Date(iso);
    if (!Number.isFinite(value.getTime())) throw new Error("Некорректное время записи.");
    const options={year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hourCycle:"h23"};
    if(timeZone)options.timeZone=timeZone;
    const parts=new Intl.DateTimeFormat("en-CA",options).formatToParts(value);
    const result={};
    parts.forEach((part)=>{if(part.type!=="literal")result[part.type]=part.value});
    return {date:`${result.year}-${result.month}-${result.day}`,hour:Number(result.hour),minute:Number(result.minute)};
  }
  function zonedLocalToIso(dateValue, hourValue, minuteValue, timeZone) {
    const match=/^(\d{4})-(\d{2})-(\d{2})$/.exec(String(dateValue||""));
    const hour=Number(hourValue),minute=Number(minuteValue);
    if(!match||!Number.isInteger(hour)||hour<0||hour>23||!Number.isInteger(minute)||minute<0||minute>59)throw new Error("Выберите корректные дату и время.");
    const desired=Date.UTC(Number(match[1]),Number(match[2])-1,Number(match[3]),hour,minute);
    let guess=desired;
    for(let i=0;i<3;i+=1){
      const observed=zonedDateTimeParts(new Date(guess).toISOString(),timeZone);
      const observedUtc=Date.UTC(Number(observed.date.slice(0,4)),Number(observed.date.slice(5,7))-1,Number(observed.date.slice(8,10)),observed.hour,observed.minute);
      guess+=desired-observedUtc;
    }
    const check=zonedDateTimeParts(new Date(guess).toISOString(),timeZone);
    if(check.date!==String(dateValue)||check.hour!==hour||check.minute!==minute)throw new Error("Такого местного времени нет в выбранном часовом поясе.");
    return new Date(guess).toISOString();
  }
  function selectOptions(values, selected) {
    return values.map((value)=>`<option value="${value}" ${Number(value)===Number(selected)?"selected":""}>${String(value).padStart(2,"0")}</option>`).join("");
  }
  function minuteValues(step, current) {
    const safeStep=[15,30,60].includes(Number(step))?Number(step):30;
    const values=[];for(let value=0;value<60;value+=safeStep)values.push(value);
    if(!values.includes(Number(current)))values.push(Number(current));
    return values.sort((a,b)=>a-b);
  }
  function slugOf(p) { return String(p&&p.screen&&p.screen.slug||location.pathname.split("/").filter(Boolean).pop()||""); }
  function vapidBytes(value){const pad="=".repeat((4-value.length%4)%4),raw=atob((value+pad).replace(/-/g,"+").replace(/_/g,"/")),out=new Uint8Array(raw.length);for(let i=0;i<raw.length;i++)out[i]=raw.charCodeAt(i);return out}
  async function subscribePush(slug,mid,audience,did){if(!('serviceWorker'in navigator)||!('PushManager'in global))throw new Error('Уведомления не поддерживаются этим браузером.');const permission=await Notification.requestPermission();if(permission!=="granted")throw new Error('Разрешение на уведомления не выдано.');const key=await json(`/api/screen/${encodeURIComponent(slug)}/push/vapid-public-key`),reg=await navigator.serviceWorker.ready;let sub=await reg.pushManager.getSubscription();if(!sub)sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:vapidBytes(key.application_server_key||key.public_key)});await json(`/api/screen/${encodeURIComponent(slug)}/booking/${encodeURIComponent(mid)}/push/subscribe`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({audience,device_id:did||'',subscription:sub.toJSON()})});return true}

  function bindPublic(el, payload) {
    if (el.dataset.bookingBound) return; el.dataset.bookingBound="1";
    const body=el.querySelector(".bk-body"),mid=el.dataset.moduleId,slug=slugOf(payload),did=deviceId(mid);
    let selectedDate="",loadedDate="",selected="",service="basic",state=null;
    async function load(){try{const requestedWeek=selectedDate?mondayIsoForDate(selectedDate):"";state=await json(`/api/screen/${encodeURIComponent(slug)}/booking/${encodeURIComponent(mid)}?week=${requestedWeek}&service_id=${encodeURIComponent(service)}&device_id=${encodeURIComponent(did)}`);service=state.service_id||service;if(!selectedDate)selectedDate=state.today||state.days[0].date;loadedDate=selectedDate;render()}catch(e){if(state){selectedDate=loadedDate||state.today;render();body.insertAdjacentHTML("afterbegin",`<div class="bk-error">${esc(e.message)}</div>`)}else{body.innerHTML=`<div class="bk-error">${esc(e.message)}</div><button data-a="retry">Повторить</button>`;body.querySelector("[data-a=retry]").onclick=load}}}
    function render(){const c=state.config,l=c.labels,services=c.services.filter(x=>x.active!==false);if(!services.some(x=>x.id===service))service=services[0].id;const day=state.days.find(d=>d.date===selectedDate)||state.days[0];
      body.innerHTML=`<div class="bk-toolbar"><button data-a="prev">←</button><button data-a="today">Текущая неделя</button><button data-a="next">→</button><select name="service">${services.map(s=>`<option value="${esc(s.id)}" ${s.id===service?"selected":""}>${esc(s.title)} · ${s.duration_min} мин</option>`).join("")}</select><button data-a="notify">Включить уведомления</button></div>${c.paused?`<div class="bk-error">${esc(c.pause_message)}</div>`:""}<div class="bk-days">${state.days.map((d,i)=>`<div class="bk-day"><strong>${weekday[i]} ${d.date.slice(8,10)}.${d.date.slice(5,7)}</strong>${d.slots.length?d.slots.map(s=>`<button class="bk-slot" data-start="${esc(s.start_at)}">${esc(s.label)}</button>`).join(""):`<span class="bk-muted">Нет мест</span>`}</div>`).join("")}</div><form class="bk-form"><input name="family_name" placeholder="${esc(l.family_name)}" required><input name="given_name" placeholder="${esc(l.given_name)}" required><input name="phone" type="tel" placeholder="${esc(l.phone)}" required><button ${c.paused?"disabled":""}>Создать запись</button></form><div class="bk-msg"></div><h3>Записи на этом устройстве</h3><div class="bk-list">${state.mine.length?state.mine.map(x=>`<div class="bk-card"><strong>${fmt(x.start_at)}</strong> · ${esc(x.service_title)}<br><span class="bk-muted">${esc(statuses[x.status]||x.status)}</span> ${x.can_request_cancel?`<button data-cancel="${x.id}">Запросить отмену</button>`:""}</div>`).join(""):`<span class="bk-muted">Пока нет записей.</span>`}</div>`;
      body.querySelector("[data-a=today]").textContent="Сегодня";
      body.querySelectorAll(".bk-day").forEach((node,i)=>{if(state.days[i]!==day){node.remove();return}node.querySelector("strong").textContent=dayTitle(day.date);node.querySelectorAll(".bk-slot").forEach((button,j)=>{const slot=day.slots[j],status=slot&&slot.status||"free",available=status==="free"&&slot.available!==false;button.dataset.available=available?"1":"0";button.classList.add(status==="cancel_requested"?"bk-slot--cancel":status==="booked"?"bk-slot--booked":"bk-slot--free");button.disabled=!available})});
      body.querySelector(".bk-days").insertAdjacentHTML("afterend",'<div class="bk-legend"><span><i class="bk-dot" style="background:var(--bk-free-bg)"></i>Свободно</span><span><i class="bk-dot" style="background:var(--bk-booked-bg)"></i>Занято</span><span><i class="bk-dot" style="background:var(--bk-cancel-bg)"></i>Запрошена отмена</span></div>');
      body.querySelectorAll(".bk-list .bk-card strong").forEach((node,i)=>{if(state.mine[i])node.textContent=fmt(state.mine[i].start_at,state.timezone)});
      body.querySelectorAll("[data-start][data-available=\"1\"]").forEach(b=>b.onclick=()=>{selected=b.dataset.start;body.querySelectorAll(".bk-slot").forEach(x=>x.classList.toggle("is-selected",x===b))});
      body.querySelector("[data-a=prev]").onclick=()=>{selectedDate=addIsoDays(selectedDate,-1);selected="";load()};body.querySelector("[data-a=next]").onclick=()=>{selectedDate=addIsoDays(selectedDate,1);selected="";load()};body.querySelector("[data-a=today]").onclick=()=>{selectedDate=state.today;selected="";load()};body.querySelector("[name=service]").onchange=e=>{service=e.target.value;selected="";load()};
      body.querySelector("[data-a=notify]").onclick=async e=>{try{await subscribePush(slug,mid,'device',did);e.target.textContent='Уведомления включены';e.target.disabled=true}catch(x){alert(x.message)}};
      body.querySelector("form").onsubmit=async e=>{e.preventDefault();const m=body.querySelector(".bk-msg");if(!selected){m.innerHTML='<div class="bk-error">Сначала выберите время.</div>';return}const f=new FormData(e.currentTarget);try{await json(`/api/screen/${encodeURIComponent(slug)}/booking/${encodeURIComponent(mid)}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device_id:did,service_id:service,start_at:selected,family_name:f.get("family_name"),given_name:f.get("given_name"),phone:f.get("phone")})});selected="";await load()}catch(x){m.innerHTML=`<div class="bk-error">${esc(x.message)}</div>`}};
      body.querySelectorAll("[data-cancel]").forEach(b=>b.onclick=async()=>{try{await json(`/api/screen/${encodeURIComponent(slug)}/booking/${encodeURIComponent(mid)}/${b.dataset.cancel}/cancel-request`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({device_id:did})});await load()}catch(x){alert(x.message)}});
    }load();
  }

  function bindManager(el,payload) {
    if(el.dataset.bookingBound)return;
    el.dataset.bookingBound="1";
    const body=el.querySelector(".bk-body"),mid=el.dataset.moduleId,slug=slugOf(payload),hideKey=`gs_booking_hide_cancelled_${mid}`,hidePastKey=`gs_booking_hide_past_${mid}`;
    let state=null,hideCancelled=true,hidePast=true;
    try{hideCancelled=localStorage.getItem(hideKey)!=="0";hidePast=localStorage.getItem(hidePastKey)!=="0"}catch(_){}
    const managerBase=`/api/screen/${encodeURIComponent(slug)}/booking-admin/${encodeURIComponent(mid)}`;
    async function load(){try{state=await json(managerBase);render()}catch(e){body.innerHTML=`<div class="bk-error">${esc(e.message)}</div>`}}
    function openMoveEditor(button) {
      body.querySelectorAll(".bk-move-row").forEach((row)=>row.remove());
      const bookingId=Number(button.dataset.id);
      const item=state.bookings.find((booking)=>Number(booking.id)===bookingId);
      const sourceRow=button.closest("tr[data-booking-id]");
      if(!item||!sourceRow)return;
      let parts;
      try{parts=zonedDateTimeParts(item.start_at,state.timezone)}catch(error){alert(error.message);return}
      const moveRow=document.createElement("tr");
      moveRow.className="bk-move-row";
      moveRow.innerHTML=`<td colspan="5"><form class="bk-move-form">
        <strong>Перенос: ${esc(item.family_name)} ${esc(item.given_name)}</strong>
        <div class="bk-move-fields">
          <label>Дата<input name="date" type="date" value="${parts.date}" required></label>
          <label>Часы<select name="hour">${selectOptions(Array.from({length:24},(_,index)=>index),parts.hour)}</select></label>
          <label>Минуты<select name="minute">${selectOptions(minuteValues(state.config.step_min,parts.minute),parts.minute)}</select></label>
        </div>
        <div class="bk-muted">Часовой пояс: ${esc(state.timezone||"локальный")}. Минуты идут с шагом ${Number(state.config.step_min)||30}.</div>
        <div class="bk-move-actions"><button type="submit">Сохранить перенос</button><button type="button" data-a="cancel-move">Закрыть</button><div class="bk-msg"></div></div>
      </form></td>`;
      sourceRow.insertAdjacentElement("afterend",moveRow);
      const form=moveRow.querySelector("form");
      form.querySelector('[data-a="cancel-move"]').onclick=()=>moveRow.remove();
      form.onsubmit=async(event)=>{
        event.preventDefault();
        const message=form.querySelector(".bk-msg"),submit=form.querySelector('button[type="submit"]');
        try{
          submit.disabled=true;
          const startAt=zonedLocalToIso(form.elements.date.value,form.elements.hour.value,form.elements.minute.value,state.timezone);
          await json(`${managerBase}/${bookingId}/move`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({start_at:startAt})});
          await load();
        }catch(error){
          submit.disabled=false;
          message.innerHTML=`<div class="bk-error">${esc(error.message)}</div>`;
        }
      };
      moveRow.querySelector('input[name="date"]').focus();
      if(moveRow.scrollIntoView)moveRow.scrollIntoView({block:"nearest",behavior:"smooth"});
    }
    function render(){
      const c=state.config,l=c.labels;
      body.innerHTML=`<div class="bk-toolbar"><button data-a="prev">←</button><button data-a="today">Текущая неделя</button><button data-a="next">→</button><span>${esc(state.week_start)}</span><button data-a="notify">Уведомлять обо всех изменениях</button></div><details><summary>Создать запись вручную</summary><form class="bk-create bk-grid"><select name="service_id">${c.services.filter(x=>x.active!==false).map(x=>`<option value="${esc(x.id)}">${esc(x.title)}</option>`).join('')}</select><input name="start_at" type="datetime-local" required><input name="family_name" placeholder="${esc(l.family_name)}" required><input name="given_name" placeholder="${esc(l.given_name)}" required><input name="phone" placeholder="${esc(l.phone)}" required><button>Создать</button></form></details><table><thead><tr><th>Время</th><th>${esc(l.person)}</th><th>${esc(l.service)}</th><th>Состояние</th><th></th></tr></thead><tbody>${state.bookings.length?state.bookings.map(x=>`<tr data-booking-id="${x.id}"><td>${fmt(x.start_at)}</td><td>${esc(x.family_name)} ${esc(x.given_name)}<br>${esc(x.phone)}</td><td>${esc(x.service_title)}</td><td>${esc(statuses[x.status]||x.status)}</td><td><div class="bk-actions">${x.status==='cancel_requested'?`<button data-id="${x.id}" data-action="confirm_cancel">Подтвердить отмену</button><button data-id="${x.id}" data-action="reject_cancel">Отклонить</button>`:""}${x.status!=='cancelled'?`<button data-id="${x.id}" data-action="move">Перенести</button><button data-id="${x.id}" data-action="cancel">Отменить</button>`:""}</div></td></tr>`).join(""):`<tr><td colspan="5">Записей нет.</td></tr>`}</tbody></table><details><summary>Настройки модуля</summary><form class="bk-settings"><div class="bk-grid">${Object.entries(l).map(([k,v])=>`<label>${esc(labelNames[k]||k)}<input data-label="${esc(k)}" value="${esc(v)}"></label>`).join("")}<label>Шаг времени<select name="step_min"><option>15</option><option>30</option><option>60</option></select></label><label><input name="paused" type="checkbox" ${c.paused?"checked":""}> Приостановить новые записи</label><label>Сообщение<input name="pause_message" value="${esc(c.pause_message)}"></label></div><label>Услуги: название | длительность<textarea name="services">${esc(c.services.map(x=>`${x.title} | ${x.duration_min}`).join("\n"))}</textarea></label><label>Интервалы Пн–Вс: 09:00-18:00; несколько через запятую<textarea name="windows">${esc(Array.from({length:7},(_,i)=>`${weekday[i]}: ${(c.weekly_windows[i]||[]).map(x=>x.join("-")).join(", ")}`).join("\n"))}</textarea></label><button>Сохранить настройки</button><div class="bk-msg"></div></form></details>`;
      body.querySelectorAll('[data-a=prev],[data-a=today],[data-a=next]').forEach(button=>button.remove());
      const scopeLabel=body.querySelector('.bk-toolbar span');
      if(scopeLabel)scopeLabel.textContent='Все записи';
      const bookingsById=new Map(state.bookings.map((item)=>[String(item.id),item]));
      body.querySelectorAll('tbody tr[data-booking-id]').forEach((row)=>{
        const item=bookingsById.get(String(row.dataset.bookingId));
        if(item)row.querySelector('td').textContent=fmt(item.start_at,state.timezone);
      });
      const filter=document.createElement('label'),pastFilter=document.createElement('label');
      filter.className=pastFilter.className='bk-filter';
      filter.innerHTML=`<input type="checkbox" ${hideCancelled?'checked':''}> Скрыть отменённые`;
      pastFilter.innerHTML=`<input type="checkbox" ${hidePast?'checked':''}> Скрыть прошедшие`;
      body.querySelector('.bk-toolbar').append(filter,pastFilter);
      const applyFilter=()=>{
        const now=new Date(state.now).getTime();
        body.querySelectorAll('tbody tr[data-booking-id]').forEach((row)=>{
          const item=bookingsById.get(String(row.dataset.bookingId));
          if(!item)return;
          const isPast=new Date(item.end_at).getTime()<=now;
          row.classList.toggle('bk-row--cancel-requested',item.status==='cancel_requested');
          row.classList.toggle('bk-row--hidden',(hideCancelled&&item.status==='cancelled')||(hidePast&&isPast));
          row.style.opacity=isPast?'.62':'';
        });
      };
      filter.querySelector('input').onchange=e=>{hideCancelled=e.target.checked;try{localStorage.setItem(hideKey,hideCancelled?'1':'0')}catch(_){}applyFilter()};
      pastFilter.querySelector('input').onchange=e=>{hidePast=e.target.checked;try{localStorage.setItem(hidePastKey,hidePast?'1':'0')}catch(_){}applyFilter()};
      applyFilter();
      body.querySelector('[name=step_min]').value=String(c.step_min);
      body.querySelector('[data-a=notify]').onclick=async e=>{try{await subscribePush(slug,mid,'admin','');e.target.textContent='Уведомления включены';e.target.disabled=true}catch(x){alert(x.message)}};
      body.querySelector('.bk-create').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.currentTarget),local=new Date(f.get('start_at'));try{await json(managerBase,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({screen_slug:slug,service_id:f.get('service_id'),start_at:local.toISOString(),family_name:f.get('family_name'),given_name:f.get('given_name'),phone:f.get('phone')})});load()}catch(x){alert(x.message)}};
      body.querySelectorAll('[data-action]').forEach(button=>button.onclick=async()=>{
        if(button.dataset.action==='move'){openMoveEditor(button);return}
        try{await json(`${managerBase}/${button.dataset.id}/${button.dataset.action}`,{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});load()}catch(x){alert(x.message)}
      });
      body.querySelector('.bk-settings').onsubmit=async e=>{e.preventDefault();const f=e.currentTarget,labels={};f.querySelectorAll('[data-label]').forEach(x=>labels[x.dataset.label]=x.value);const services=f.services.value.split(/\r?\n/).map((line,i)=>{const p=line.split('|');return{id:`service-${i+1}`,title:(p[0]||'').trim(),duration_min:Number(p[1])||Number(f.step_min.value),active:true}}).filter(x=>x.title);const weekly_windows={};f.windows.value.split(/\r?\n/).forEach((line,i)=>{const rest=line.replace(/^[^:]+:\s*/,"");weekly_windows[String(i)]=rest.split(',').map(x=>x.trim().split('-')).filter(x=>x.length===2)});try{await json(`${managerBase}/config`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({},c,{labels,services,weekly_windows,step_min:Number(f.step_min.value),paused:f.paused.checked,pause_message:f.pause_message.value}))});load()}catch(x){f.querySelector('.bk-msg').innerHTML=`<div class="bk-error">${esc(x.message)}</div>`}};
    }
    load();
  }
  function bind(root,payload){root.querySelectorAll('.gs-booking[data-booking-kind]').forEach(el=>el.dataset.bookingKind==='public'?bindPublic(el,payload):bindManager(el,payload))}
  global.GuardSchoolBooking={bind};
})(typeof window !== "undefined" ? window : globalThis);
