const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const React = require("react");
const RS = require("react-dom/server");
const fa = require("react-icons/fa");
const { applyTheme } = require(process.env.SKILL + "/scripts/apply_theme.js");

const FONT = "Fedra Sans Pro (Основной текст)";
// Брендовый серый = Pantone 447 C #484E41 (оливково-серый). Зелёный Green C — только в мелких акцентах.
const THEME = {
  name: "iway HR", headFontFace: FONT, bodyFontFace: FONT,
  colors: { dk1: "484E41", lt1: "FFFFFF", dk2: "5A6055", lt2: "F3F5F1", accent1: "009634", accent2: "484E41", accent3: "007026", accent4: "C9EDDA", accent5: "E4F1E8", accent6: "626D5B", hlink: "007026", folHlink: "626D5B" },
};
const G = "009634", GD = "007026", MINT = "C9EDDA", MINT2 = "E4F1E8";
const OL = "484E41", BODY = "5A6055", WHITE = "FFFFFF", SOFT = "F3F5F1", RULE = "D5D9CF";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
pres.title = "Отдел HR i’way — знакомство для новых сотрудников";
pres.author = "HR i’way"; pres.company = "i’way";
const C = pres.SchemeColor;
const W = 13.333, H = 7.5, MX = 0.8, CW = W - 2 * MX;
const I = (f) => "img/" + f;

const iconCache = {};
async function icon(Comp, color, px = 256) {
  const key = Comp.name + color;
  if (!iconCache[key]) {
    const svg = RS.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(px) }));
    iconCache[key] = "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
  }
  return iconCache[key];
}
const T = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, valign: "top", ...o });
const card = (s, x, y, w, h, name, o = {}) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: o.r || 0.12, fill: { color: o.fill || WHITE }, line: { color: o.line || OL, width: o.lw || 1 }, objectName: name });
const circ = (s, x, y, d, fill, name) => s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: name });
const hline = (s, x, y, w, color = RULE) => s.addShape(pres.shapes.LINE, { x, y, w, h: 0, line: { color, width: 1 }, objectName: "Линия" });
async function badge(s, Comp, x, y, d = 0.6, fill = OL, name = "Иконка") {
  circ(s, x, y, d, fill, name);
  s.addImage({ data: await icon(Comp, WHITE), x: x + d * 0.27, y: y + d * 0.27, w: d * 0.46, h: d * 0.46, altText: "" });
}
async function pill(s, text, Comp, x = MX, y = 0.75) {
  const w = text.length * 0.115 + 0.5 + (Comp ? 0.32 : 0);
  s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h: 0.36, rectRadius: 0.08, fill: { color: MINT }, line: { color: MINT, width: 0 }, objectName: "Тег " + text });
  if (Comp) s.addImage({ data: await icon(Comp, GD), x: x + 0.14, y: y + 0.09, w: 0.18, h: 0.18, altText: "" });
  T(s, text.toUpperCase(), { x: x + (Comp ? 0.4 : 0.2), y, w: w - (Comp ? 0.5 : 0.4), h: 0.36, fontSize: 10, bold: true, color: GD, charSpacing: 1.5, valign: "middle" });
  return w;
}
const logoD = (s, x, y, w) => s.addImage({ path: I("logo.png"), x, y, w, h: w * 785 / 1556, objectName: "Логотип", altText: "i’way" });
const logoW = (s, x, y, w) => s.addImage({ path: I("logo_light.png"), x, y, w, h: w * 206 / 480, objectName: "Логотип", altText: "i’way" });
const para = (s, text, o = {}) => T(s, text, { x: MX, y: 2.05, w: 10.5, h: 0.7, fontSize: 16, color: BODY, ...o });

// ---------- masters
const ttl = (o = {}) => ({ name: "title", type: "title", x: MX, y: 1.2, w: CW, h: 0.75, fontSize: 36, bold: true, color: C.text1, margin: 0, valign: "top", align: "left", fit: "none", ...o });
const sn = { x: W - MX - 0.6, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: BODY, align: "right" };
const logoObj = { image: { path: I("logo.png"), x: W - MX - 0.85, y: 0.62, w: 0.85, h: 0.85 * 785 / 1556 } };
pres.defineSlideMaster({ title: "Контент", background: { color: WHITE }, objects: [logoObj, { placeholder: { options: ttl(), text: "" } }], slideNumber: sn });
pres.defineSlideMaster({ title: "Титул", background: { color: WHITE }, objects: [{ placeholder: { options: ttl({ x: MX, y: 2.2, w: 6.2, h: 2.2, fontSize: 54 }), text: "" } }] });
pres.defineSlideMaster({ title: "Раздел", background: { color: OL }, objects: [{ placeholder: { options: ttl({ color: C.background1, y: 4.45, w: 7.5, h: 1.0, fontSize: 52 }), text: "" } }] });
pres.defineSlideMaster({ title: "Финал", background: { color: OL }, objects: [{ placeholder: { options: ttl({ color: C.background1, y: 2.1, w: 6.4, h: 1.3, fontSize: 72 }), text: "" } }] });

(async () => {
  // 1 ============ ТИТУЛ
  {
    const s = pres.addSlide({ masterName: "Титул" });
    logoD(s, MX, 0.7, 1.7);
    await pill(s, "Знакомство с отделом HR", fa.FaUsers, MX, 1.65);
    s.addText("Привет!\nМы — HR i’way", { placeholder: "title" });
    T(s, "Чем занимаемся, как живёт компания и почему здесь классно работать", { x: MX, y: 4.65, w: 5.8, h: 0.9, fontSize: 18, color: BODY });
    T(s, [{ text: "Юлия Немчинова", options: { bold: true, color: OL, breakLine: true } }, { text: "Руководитель HR-отдела", options: { color: BODY } }], { x: MX, y: 6.1, w: 5, h: 0.7, fontSize: 16 });
    s.addImage({ path: I("H_hero.png"), x: 7.25, y: 0.7, w: 5.3, h: 6.1, objectName: "Фото", altText: "Девушка на фоне города" });
    s.addNotes("Приветствие. За 30 минут познакомимся с отделом HR, культурой i’way и командой.");
  }

  // 2 ============ ПЛАН
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "План встречи", fa.FaClipboardList);
    s.addText("Что нас ждёт", { placeholder: "title" });
    para(s, "Расскажем о трёх вещах — и закончим мини-квизом, чтобы проверить, что запомнилось.");
    const c = [[fa.FaUsers, "Отдел HR", "Кто мы и как заботимся о тебе на каждом этапе пути"], [fa.FaHeart, "Культура i’way", "Миссия, ценности и наши правила игры"], [fa.FaStar, "Команда i’way", "Руководство, коллеги и цифры, которыми мы гордимся"]];
    const cw = 3.75, gap = (CW - 3 * cw) / 2;
    for (let i = 0; i < 3; i++) {
      const x = MX + i * (cw + gap), y = 3.2;
      card(s, x, y, cw, 2.9, "Блок " + c[i][1]);
      await badge(s, c[i][0], x + 0.35, y + 0.35, 0.7);
      T(s, "0" + (i + 1), { x: x + cw - 1.2, y: y + 0.35, w: 0.85, h: 0.7, fontSize: 28, bold: true, color: "B9BFB1", align: "right", valign: "middle" });
      T(s, c[i][1], { x: x + 0.35, y: y + 1.3, w: cw - 0.7, h: 0.45, fontSize: 22, bold: true, color: OL });
      T(s, c[i][2], { x: x + 0.35, y: y + 1.85, w: cw - 0.7, h: 0.9, fontSize: 15, color: BODY });
    }
    s.addNotes("Три блока: HR, культура, команда. В конце — квиз из трёх вопросов.");
  }

  // dividers
  const divider = async (n, title, sub, Comp) => {
    const s = pres.addSlide({ masterName: "Раздел" });
    T(s, n, { x: MX, y: 0.8, w: 7, h: 3.4, fontSize: 200, bold: true, color: MINT });
    s.addText(title, { placeholder: "title" });
    T(s, sub, { x: MX, y: 5.6, w: 7.5, h: 0.6, fontSize: 22, color: MINT });
    s.addShape(pres.shapes.OVAL, { x: 8.6, y: 1.7, w: 3.6, h: 3.6, fill: { color: OL }, line: { color: MINT, width: 2 }, objectName: "Круг" });
    s.addImage({ data: await icon(Comp, MINT), x: 9.75, y: 2.85, w: 1.3, h: 1.3, altText: "" });
    logoW(s, W - MX - 1.2, 0.7, 1.2);
    return s;
  };
  await divider("01", "Отдел HR", "Кто мы и чем занимаемся", fa.FaUsers);

  // 4 ============ ГЛАВНАЯ ЗАДАЧА
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Отдел HR", fa.FaUsers);
    s.addText("Главная задача отдела HR", { placeholder: "title" });
    T(s, [
      { text: "Создать такую экосистему внутри компании, где таланты могут " },
      { text: "раскрываться", options: { bold: true, color: G } }, { text: ", а бизнес — " },
      { text: "расти", options: { bold: true, color: G } },
      { text: " благодаря слаженной и эффективной работе всей команды." },
    ], { x: MX, y: 2.5, w: 7.6, h: 4.0, fontSize: 30, color: OL, valign: "middle" });
    const it = [[fa.FaSeedling, "Таланты раскрываются", "Помогаем каждому найти своё место и расти"], [fa.FaChartLine, "Бизнес растёт", "Сильная команда — сильная компания"]];
    for (let i = 0; i < 2; i++) {
      const y = 2.5 + i * 2.1;
      card(s, 8.95, y, 3.58, 1.9, "Карточка " + it[i][1]);
      await badge(s, it[i][0], 9.25, y + 0.3, 0.6);
      T(s, it[i][1], { x: 10.05, y: y + 0.3, w: 2.3, h: 0.6, fontSize: 17, bold: true, color: OL, valign: "middle" });
      T(s, it[i][2], { x: 9.25, y: y + 1.05, w: 3.0, h: 0.7, fontSize: 14, color: BODY });
    }
    s.addNotes("Формулировка главной задачи — без изменений.");
  }

  // 5 ============ КОМАНДА HR
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Отдел HR", fa.FaUsers);
    s.addText("Знакомьтесь: команда HR", { placeholder: "title" });
    para(s, "Мы всегда рядом: пишите и заходите в любое время — будем рады поговорить.");
    const p = [["P_julia.png", "Юлия Немчинова", "Руководитель отдела HR"], ["P_anna.png", "Анна Шулятицкая", "Ведущий HR-специалист"], ["P_elena.png", "Елена Таратынова", "Офис-менеджер"]];
    const cw = 3.75, gap = (CW - 3 * cw) / 2;
    p.forEach((r, i) => {
      const x = MX + i * (cw + gap), y = 2.85;
      card(s, x, y, cw, 3.95, "Карточка " + r[1]);
      s.addImage({ path: I(r[0]), x: x + 0.2, y: y + 0.2, w: 3.35, h: 2.5, objectName: r[1], altText: r[1] });
      T(s, r[1], { x: x + 0.3, y: y + 2.95, w: cw - 0.6, h: 0.4, fontSize: 20, bold: true, color: OL });
      T(s, r[2], { x: x + 0.3, y: y + 3.4, w: cw - 0.6, h: 0.4, fontSize: 15, color: BODY });
    });
    s.addNotes("Представить каждого: роль и зоны ответственности.");
  }

  // 6 ============ EJM — дорожная карта
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Employee Journey Map", fa.FaMapMarkerAlt);
    s.addText("Мы рядом на всём твоём пути", { placeholder: "title" });
    para(s, "Дорожная карта сотрудника: на каждом этапе у нас есть, чем помочь.");
    const st = [[fa.FaHandshake, "Найм", "Знакомимся и зовём в команду"], [fa.FaSeedling, "Адаптация", "Помогаем влиться и освоиться"], [fa.FaHeart, "Вовлечённость", "Чтобы было интересно и тепло"], [fa.FaGraduationCap, "Обучение", "Делимся знаниями и навыками"], [fa.FaChartLine, "Рост и развитие", "Двигаемся вперёд вместе"], [fa.FaBullhorn, "HR-бренд", "Рассказываем, какие мы"]];
    const cw = 3.1, c0 = MX + cw / 2, c1 = W - MX - cw / 2, step = (c1 - c0) / 5, ry = 4.61;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX, y: ry - 0.11, w: CW, h: 0.22, rectRadius: 0.11, fill: { color: "E3E6DD" }, line: { color: "E3E6DD", width: 0 }, objectName: "Дорога" });
    s.addShape(pres.shapes.LINE, { x: MX + 0.2, y: ry, w: CW - 0.4, h: 0, line: { color: "9AA392", width: 1.25, dashType: "dash" }, objectName: "Разметка" });
    for (let i = 0; i < 6; i++) {
      const cx = c0 + i * step, up = i % 2 === 0, cy = up ? 2.75 : 5.25, ch = 1.3;
      card(s, cx - cw / 2, cy, cw, ch, "Этап " + st[i][1]);
      T(s, "0" + (i + 1), { x: cx - cw / 2 + 0.25, y: cy + 0.2, w: 0.5, h: 0.35, fontSize: 14, bold: true, color: G, valign: "middle" });
      T(s, st[i][1], { x: cx - cw / 2 + 0.75, y: cy + 0.2, w: cw - 0.95, h: 0.35, fontSize: 17, bold: true, color: OL, valign: "middle" });
      T(s, st[i][2], { x: cx - cw / 2 + 0.25, y: cy + 0.68, w: cw - 0.5, h: 0.5, fontSize: 14, color: BODY });
      s.addShape(pres.shapes.LINE, { x: cx, y: up ? cy + ch : ry + 0.36, w: 0, h: up ? ry - 0.36 - (cy + ch) : cy - (ry + 0.36), line: { color: OL, width: 1.25 }, objectName: "Выноска " + (i + 1) });
      await badge(s, st[i][0], cx - 0.36, ry - 0.36, 0.72, i === 5 ? G : OL, "Веха " + st[i][1]);
    }
    s.addNotes("Шесть этапов пути сотрудника — как дорожная карта. Дальше подробнее про найм, адаптацию и HR-бренд.");
  }

  // 7 ============ НАЙМ
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "EJM · Найм", fa.FaHandshake);
    s.addText("Найм: как мы собираем команду", { placeholder: "title" });
    para(s, "От отклика до первого рабочего дня — так выглядела наша воронка.");
    const f = [["Отклики", 5866], ["Первый контакт", 1038], ["Приглашение на собеседование", 743], ["Собеседование", 576], ["Оффер", 100], ["Выход на работу", 95]];
    const x0 = MX, lw = 3.4, bx = x0 + lw + 0.2, bmax = 3.2, y0 = 3.05;
    f.forEach((r, i) => {
      const y = y0 + i * 0.62;
      hline(s, x0, y - 0.04, 8.5);
      T(s, r[0], { x: x0, y, w: lw, h: 0.5, fontSize: 15, color: OL, valign: "middle" });
      const bw = Math.max(bmax * r[1] / 5866, 0.06);
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: bx, y: y + 0.15, w: bw, h: 0.2, rectRadius: 0.05, fill: { color: i === 5 ? G : OL }, line: { color: i === 5 ? G : OL, width: 0 }, objectName: "Столбец " + r[0] });
      T(s, String(r[1]).replace(/(\d)(?=(\d{3})$)/, "$1 "), { x: bx + 3.4, y, w: 1.3, h: 0.5, fontSize: 18, bold: true, color: i === 5 ? G : OL, align: "right", valign: "middle" });
    });
    hline(s, x0, y0 + 6 * 0.62 - 0.04, 8.5);
    T(s, "*данные на 31.12.2025", { x: x0, y: 6.85, w: 4, h: 0.3, fontSize: 11, color: BODY });
    card(s, 9.7, 3.0, 2.83, 3.7, "Итог");
    T(s, "95", { x: 9.95, y: 3.2, w: 2.4, h: 1.3, fontSize: 72, bold: true, color: G });
    T(s, "новых коллег вышли на работу", { x: 9.95, y: 4.55, w: 2.4, h: 0.9, fontSize: 16, bold: true, color: OL });
    T(s, "≈ 1 из 60 откликов", { x: 9.95, y: 5.7, w: 2.4, h: 0.7, fontSize: 14, color: BODY });
    s.addNotes("Длина столбцов пропорциональна числам. Данные на 31.12.2025.");
  }

  // 8 ============ АДАПТАЦИЯ
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "EJM · Адаптация и развитие", fa.FaSeedling);
    s.addText("Чтобы с первого дня было комфортно", { placeholder: "title" });
    s.addImage({ path: I("P_team.png"), x: MX, y: 2.4, w: 4.6, h: 4.2, objectName: "Фото команды", altText: "Команда за рабочим столом" });
    const it = [["Welcome-встреча", "Знакомимся и рассказываем, как у нас всё устроено"], ["Неделя адаптации", "Просим короткую анкету: нам важно твоё мнение"], ["Обучение", "«Игра по неподачам», «Системный руководитель», «Академия i’way»"], ["Переводы", "Поддерживаем, если решишь сменить роль или команду"]];
    for (let i = 0; i < 4; i++) {
      const x = 5.7 + (i % 2) * 3.55, y = 2.4 + Math.floor(i / 2) * 2.2;
      card(s, x, y, 3.4, 2.0, "Шаг " + it[i][0]);
      circ(s, x + 0.25, y + 0.25, 0.5, OL, "Номер " + (i + 1));
      T(s, String(i + 1), { x: x + 0.25, y: y + 0.25, w: 0.5, h: 0.5, fontSize: 16, bold: true, color: WHITE, align: "center", valign: "middle" });
      T(s, it[i][0], { x: x + 0.95, y: y + 0.25, w: 2.3, h: 0.5, fontSize: 16, bold: true, color: OL, valign: "middle" });
      T(s, it[i][1], { x: x + 0.25, y: y + 0.95, w: 2.95, h: 0.95, fontSize: 13, color: BODY });
    }
    s.addNotes("Рассказать про welcome-встречу и анкеты. Названия программ оставляем как есть.");
  }

  // 9 ============ HR-БРЕНД
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "EJM · HR-бренд", fa.FaBullhorn);
    s.addText("HR-бренд: как мы о себе рассказываем", { placeholder: "title" });
    para(s, "Снаружи нас видят кандидаты, внутри — мы сами. Работаем с обеими сторонами.");
    const cols = [[fa.FaGlobe, "Снаружи", ["Карьерные сайты: hh.ru и LinkedIn", "Наружная реклама: метро и экраны", "Работа с университетами", "Ответы на отзывы на площадках"]], [fa.FaHome, "Внутри", ["Миссия и ценности", "Внутренние коммуникации", "Мотивация и бенефиты", "EVP — уникальное ценностное предложение"]]];
    for (let c = 0; c < 2; c++) {
      const x = MX + c * 6.05, w = 5.85;
      card(s, x, 3.0, w, 3.8, "Колонка " + cols[c][1]);
      await badge(s, cols[c][0], x + 0.35, 3.3, 0.65);
      T(s, cols[c][1], { x: x + 1.2, y: 3.3, w: 3, h: 0.65, fontSize: 24, bold: true, color: OL, valign: "middle" });
      cols[c][2].forEach((t, i) => {
        const y = 4.2 + i * 0.6;
        hline(s, x + 0.35, y - 0.05, w - 0.7);
        T(s, t, { x: x + 0.35, y, w: w - 0.7, h: 0.5, fontSize: 15, color: BODY, valign: "middle" });
      });
    }
    s.addNotes("Снаружи — как нас видят кандидаты, внутри — как мы живём.");
  }

  await divider("02", "Культура i’way", "Во что мы верим и как работаем вместе", fa.FaHeart);

  // 11 ============ О КОМПАНИИ
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Культура i’way", fa.FaGlobe);
    s.addText("i’way — трансферы по всему миру", { placeholder: "title" });
    para(s, "Сервис заказа трансферов, который объединяет страны, аэропорты и людей.");
    const st = [["130+", "стран, где мы возим людей"], ["2 500+", "поездок ежедневно"], ["600+", "аэропортов мира"]];
    const cw = 3.75, gap = (CW - 3 * cw) / 2;
    st.forEach((r, i) => {
      const x = MX + i * (cw + gap);
      hline(s, x, 3.05, cw, OL);
      T(s, r[0], { x, y: 3.2, w: cw, h: 1.3, fontSize: 66, bold: true, color: G });
      T(s, r[1], { x, y: 4.55, w: cw, h: 0.5, fontSize: 18, color: OL });
    });
    const fct = [[fa.FaCalendarAlt, "с 2009", "года на рынке"], [fa.FaStar, "4,9 из 5", "оценка поездок"], [fa.FaMapMarkerAlt, "Офисы", "в Казахстане, ОАЭ, Индии"]];
    for (let i = 0; i < 3; i++) {
      const x = MX + i * (cw + gap), y = 5.45;
      card(s, x, y, cw, 1.3, "Факт " + fct[i][1]);
      await badge(s, fct[i][0], x + 0.3, y + 0.35, 0.6);
      T(s, fct[i][1], { x: x + 1.15, y: y + 0.28, w: cw - 1.4, h: 0.4, fontSize: 18, bold: true, color: OL });
      T(s, fct[i][2], { x: x + 1.15, y: y + 0.7, w: cw - 1.4, h: 0.45, fontSize: 13, color: BODY });
    }
    s.addNotes("130+ стран, 2 500+ поездок и 600+ аэропортов — из внутренней презентации. Оценка 4,9, офисы в Казахстане, ОАЭ и Индии — по данным Felo-поиска (App Store, блог i’way, Forbes.kz); проверьте актуальность.");
  }

  // 12 ============ ДАШБОРД
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Культура i’way", fa.FaChartLine);
    s.addText("Наш день в цифрах", { placeholder: "title" });
    T(s, "Бронирования, выручка и оценки клиентов — всё на одном экране, в реальном времени.", { x: MX, y: 2.5, w: 4.2, h: 1.6, fontSize: 20, color: OL });
    card(s, MX, 4.7, 4.2, 1.9, "Оценка");
    await badge(s, fa.FaStar, MX + 0.3, 5.0, 0.6);
    T(s, "4,9 из 5", { x: MX + 1.15, y: 4.95, w: 2.8, h: 0.7, fontSize: 28, bold: true, color: G, valign: "middle" });
    T(s, "средняя оценка поездок — каждый из нас влияет на эту цифру", { x: MX + 0.3, y: 5.8, w: 3.7, h: 0.7, fontSize: 13, color: BODY });
    s.addImage({ path: I("P_dash.png"), x: 5.45, y: 2.4, w: 7.1, h: 4.0, objectName: "Дашборд", altText: "Панель с онлайн-метриками" });
    s.addNotes("Скриншот внутреннего дашборда. Перед показом широкой аудитории проверьте конфиденциальность цифр.");
  }

  // 13 ============ ИСТОРИЯ — хронология
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Культура i’way · История", fa.FaCalendarAlt);
    s.addText("Как всё начиналось", { placeholder: "title" });
    s.addImage({ path: I("P_found.png"), x: MX, y: 2.4, w: 3.3, h: 4.2, objectName: "Основатели", altText: "Основатели i’way" });
    const ev = [["2009", "Основание", "ООО «Сибирская трансферная компания»"], ["2011", "Выход в онлайн", "iWay Express: запустили двуязычный сайт с онлайн-бронированием"], ["2013", "Новый бренд", "Родился бренд i’way"], ["2023", "Выход за границу", "Открыли офис в Казахстане"]];
    const lx = 5.0, y0 = 2.55, stepY = 1.15;
    s.addShape(pres.shapes.LINE, { x: lx, y: y0 + 0.15, w: 0, h: stepY * 3, line: { color: "8E9684", width: 2.5 }, objectName: "Линия времени" });
    ev.forEach((r, i) => {
      const y = y0 + i * stepY, last = i === 3;
      circ(s, lx - 0.17, y - 0.02 , 0.34, WHITE, "Точка фон");
      s.addShape(pres.shapes.OVAL, { x: lx - 0.17, y: y - 0.02, w: 0.34, h: 0.34, fill: { color: WHITE }, line: { color: last ? G : OL, width: 3 }, objectName: "Веха " + r[0] });
      T(s, r[0], { x: lx + 0.5, y: y - 0.1, w: 1.6, h: 0.55, fontSize: 32, bold: true, color: last ? G : OL, valign: "middle" });
      T(s, r[1], { x: lx + 2.2, y: y - 0.1, w: 5.4, h: 0.3, fontSize: 12, bold: true, color: G, charSpacing: 1.5 });
      T(s, r[2], { x: lx + 2.2, y: y + 0.2, w: 5.4, h: 0.7, fontSize: 16, color: OL });
    });
    s.addNotes("Даты 2009–2013 — из внутренней презентации; офис в Казахстане (начало 2023, Алматы) — Forbes.kz, по данным Felo-поиска.");
  }

  // 14 ============ МИССИЯ
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Фундамент", fa.FaFlagCheckered);
    s.addText("Наша миссия", { placeholder: "title" });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX, y: 2.3, w: CW, h: 4.4, rectRadius: 0.15, fill: { color: OL }, line: { color: OL, width: 0 }, objectName: "Миссия" });
    T(s, "i’way меняет представление о транспортном сервисе в России и мире и, ориентируясь на потребности клиентов, выступает законодателем стандартов обслуживания.", { x: MX + 0.7, y: 2.7, w: 10.2, h: 3.0, fontSize: 30, color: WHITE, valign: "middle" });
    logoW(s, MX + 0.7, 5.85, 0.95);
    s.addNotes("Миссия — формулировка без изменений.");
  }

  // 15 ============ ЦЕННОСТИ
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Бренд-код", fa.FaStar);
    s.addText("Наши ценности", { placeholder: "title" });
    const v = [
      [fa.FaDoorOpen, "Открытость", "Готовность принимать новое, прислушиваться к просьбам и проблемам клиентов; старание быть нужным."],
      [fa.FaBalanceScale, "Честность", "Соблюдение делового этикета и корпоративной политики; неприятие обмана и хитростей в корыстных целях."],
      [fa.FaFlagCheckered, "Лидерство", "Предоставление клиентам лучшего; ввод новых стандартов обслуживания."],
      [fa.FaCogs, "Технологичность", "Внедрение современных решений."],
      [fa.FaSmileBeam, "Человечность", "Уважительное отношение; дружелюбие в общении."],
    ];
    const cw = 3.75, ch = 2.15, gap = (CW - 3 * cw) / 2;
    for (let i = 0; i < 5; i++) {
      const x = MX + (i % 3) * (cw + gap), y = 2.3 + Math.floor(i / 3) * (ch + 0.25);
      card(s, x, y, cw, ch, "Ценность " + v[i][1]);
      await badge(s, v[i][0], x + 0.3, y + 0.28, 0.55);
      T(s, v[i][1], { x: x + 1.05, y: y + 0.28, w: cw - 1.3, h: 0.55, fontSize: 18, bold: true, color: OL, valign: "middle" });
      T(s, v[i][2], { x: x + 0.3, y: y + 1.0, w: cw - 0.6, h: 1.1, fontSize: 13, color: BODY });
    }
    const lx = MX + 2 * (cw + gap), ly = 2.3 + ch + 0.25;
    card(s, lx, ly, cw, ch, "Логотип", { fill: SOFT, line: RULE });
    logoD(s, lx + (cw - 1.9) / 2, ly + (ch - 1.9 * 785 / 1556) / 2, 1.9);
    s.addNotes("Ценности — формулировки из бренд-кода, без изменений.");
  }

  // 16 ============ КАК У НАС ПРИНЯТО
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Культура i’way", fa.FaHeart);
    s.addText("Как у нас принято", { placeholder: "title" });
    para(s, "Пять правил, по которым мы живём и работаем каждый день.");
    const r = [[fa.FaTshirt, "Дресс-код", "Smart Casual: выглядим опрятно и остаёмся собой"], [fa.FaUserFriends, "Руководитель рядом", "Он — первая точка входа для любого вопроса"], [fa.FaShieldAlt, "Ответственность", "Отвечаем за результат и держим слово"], [fa.FaLightbulb, "Идеи приветствуются", "Предложил полезное — поможем воплотить"], [fa.FaHeart, "Неравнодушие", "Нам не всё равно — к клиентам и друг к другу"]];
    for (let i = 0; i < 5; i++) {
      const y = 2.95 + i * 0.78;
      hline(s, MX, y - 0.06, CW);
      await badge(s, r[i][0], MX, y + 0.04, 0.55);
      T(s, r[i][1], { x: MX + 0.9, y, w: 3.6, h: 0.64, fontSize: 19, bold: true, color: OL, valign: "middle" });
      T(s, r[i][2], { x: 5.6, y, w: 6.93, h: 0.64, fontSize: 16, color: BODY, valign: "middle" });
    }
    hline(s, MX, 2.95 + 5 * 0.78 - 0.06, CW);
    s.addNotes("Пять принципов корпоративной культуры из внутренней презентации, переформулированы дружелюбнее.");
  }

  // 17 ============ АПОСТРОФ
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Маленькая деталь", fa.FaQuoteLeft);
    s.addText("Наш апостроф — особенный", { placeholder: "title" });
    card(s, MX, 2.4, 5.2, 4.3, "Плитка логотипа", { fill: SOFT, line: RULE });
    logoD(s, MX + 0.7, 3.4, 3.8);
    const rows = [["i’way", true, "Правильно — с красивым апострофом"], ["i'way", false, "Не так — прямой апостроф"], ["i`way", false, "И не так — обратный апостроф"]];
    for (let i = 0; i < 3; i++) {
      const r = rows[i], y = 2.4 + i * 1.2;
      card(s, 6.3, y, 6.23, 1.05, "Вариант " + r[0], { line: r[1] ? G : OL });
      T(s, r[0], { x: 6.6, y, w: 2.3, h: 1.05, fontSize: 30, bold: true, color: r[1] ? G : BODY, valign: "middle" });
      T(s, r[2], { x: 8.8, y, w: 2.7, h: 1.05, fontSize: 14, color: BODY, valign: "middle" });
      circ(s, 11.7, y + 0.25, 0.55, r[1] ? G : OL, r[1] ? "Верно" : "Неверно");
      s.addImage({ data: await icon(r[1] ? fa.FaCheck : fa.FaTimes, WHITE), x: 11.7 + 0.15, y: y + 0.4, w: 0.25, h: 0.25, altText: r[1] ? "верно" : "неверно" });
    }
    T(s, "Как напечатать на Windows:", { x: 6.3, y: 6.15, w: 3.1, h: 0.55, fontSize: 15, color: OL, valign: "middle" });
    [["Alt", 9.5, 0.85], ["+", 10.4, 0.35], ["0146", 10.8, 1.2]].forEach(([t, x, w]) => {
      if (t === "+") { T(s, t, { x, y: 6.15, w, h: 0.55, fontSize: 20, bold: true, color: OL, align: "center", valign: "middle" }); return; }
      card(s, x, 6.15, w, 0.55, "Клавиша " + t, { r: 0.1 });
      T(s, t, { x, y: 6.15, w, h: 0.55, fontSize: 17, bold: true, color: OL, align: "center", valign: "middle" });
    });
    s.addNotes("Пишем i’way с типографским апострофом (Alt+0146).");
  }

  await divider("03", "Команда i’way", "Люди, благодаря которым всё работает", fa.FaStar);

  // 19 ============ ДИРЕКЦИЯ
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Команда i’way", fa.FaStar);
    s.addText("Дирекция i’way", { placeholder: "title" });
    const d = [["P_d1.png", "Дмитрий Салихов", "CEO, основатель i’way"], ["P_d2.png", "Дмитрий Сарайкин", "Сооснователь i’way"], ["P_d3.png", "Александр Шведов", "CTO, исполнительный директор"], ["P_d5.png", "Джехад Абугсиса", "Директор по международному развитию"]];
    const cw = 2.8, gap = (CW - 4 * cw) / 3;
    d.forEach((p, i) => {
      const x = MX + i * (cw + gap), y = 2.2;
      card(s, x, y, cw, 4.6, "Карточка " + p[1]);
      s.addImage({ path: I(p[0]), x: x + 0.15, y: y + 0.15, w: 2.5, h: 2.9, objectName: p[1], altText: p[1] });
      T(s, p[1], { x: x + 0.2, y: y + 3.25, w: cw - 0.4, h: 0.4, fontSize: 16, bold: true, color: OL });
      T(s, p[2], { x: x + 0.2, y: y + 3.7, w: cw - 0.4, h: 0.8, fontSize: 14, color: BODY });
    });
    s.addNotes("Слайд Ольги Чикан (операционный директор) был скрыт в исходной презентации, поэтому здесь её нет.");
  }

  // 20 ============ ЦИФРЫ КОМАНДЫ
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Команда i’way", fa.FaUsers);
    s.addText("Мы — большая команда", { placeholder: "title" });
    para(s, "Разные люди и города — одна команда i’way.");
    const st = [[fa.FaUsers, "160+", "коллег в команде"], [fa.FaFemale, "100+", "девушек"], [fa.FaMale, "50+", "парней"], [fa.FaBirthdayCake, "32", "года — средний возраст"]];
    const cw = 2.8, gap = (CW - 4 * cw) / 3;
    for (let i = 0; i < 4; i++) {
      const x = MX + i * (cw + gap), y = 3.0;
      card(s, x, y, cw, 3.4, "Плитка " + st[i][2]);
      await badge(s, st[i][0], x + 0.35, y + 0.35, 0.65);
      T(s, st[i][1], { x: x + 0.35, y: y + 1.25, w: cw - 0.5, h: 1.1, fontSize: 56, bold: true, color: G });
      T(s, st[i][2], { x: x + 0.35, y: y + 2.5, w: cw - 0.6, h: 0.7, fontSize: 16, color: OL });
    }
    s.addNotes("Данные из внутренней презентации.");
  }

  // 21 ============ КАРТА
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Команда i’way", fa.FaGlobe);
    s.addText("Где нас можно встретить", { placeholder: "title" });
    s.addImage({ path: I("P_map.png"), x: MX, y: 2.3, w: 8.2, h: 4.5, objectName: "Карта", altText: "Карта присутствия i’way" });
    card(s, 9.3, 2.3, 3.23, 4.5, "Подпись");
    await badge(s, fa.FaMapMarkerAlt, 9.65, 2.65, 0.65);
    T(s, "Города России и страны, где работает i’way", { x: 9.65, y: 3.55, w: 2.55, h: 1.5, fontSize: 18, bold: true, color: OL });
    T(s, "Мы всё ближе к клиентам и партнёрам по всему миру", { x: 9.65, y: 5.2, w: 2.55, h: 1.3, fontSize: 14, color: BODY });
    s.addNotes("Города России и страны присутствия — по карте.");
  }

  // 22–24 ============ КВИЗ
  const quiz = async (n, q, A, B, right, note) => {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, `Мини-квиз · вопрос ${n} из 3`, fa.FaLightbulb);
    s.addText(q, { placeholder: "title" });
    [A, B].forEach((t, i) => {
      const x = MX + i * 6.05;
      card(s, x, 2.8, 5.85, 3.0, "Вариант " + "AB"[i]);
      circ(s, x + 0.4, 3.15, 0.75, OL, "Буква " + "AB"[i]);
      T(s, "AB"[i], { x: x + 0.4, y: 3.15, w: 0.75, h: 0.75, fontSize: 26, bold: true, color: WHITE, align: "center", valign: "middle" });
      T(s, t, { x: x + 0.4, y: 4.2, w: 5.05, h: 1.4, fontSize: 22, bold: true, color: OL });
    });
    s.addNotes("Правильный ответ: " + "AB"[right] + ". " + note);
  };
  await quiz(1, "Какая главная задача отдела HR?", "Укомплектованность штата", "Создать сильную команду для роста компании", 1, "Создать сильную команду для роста компании.");
  await quiz(2, "Ценность «открытость» — это…", "Готовность принимать новое и прислушиваться к потребностям клиентов", "Принцип «открытых дверей»: с идеей можно прийти к руководителю", 0, "Готовность принимать новое и прислушиваться к потребностям клиентов.");
  await quiz(3, "Кто в i’way главный?", "Клиент", "CEO", 0, "Клиент.");

  // 25 ============ ОТВЕТЫ
  {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Мини-квиз · ответы", fa.FaCheck);
    s.addText("Проверяем себя", { placeholder: "title" });
    const a = [["1", "Главная задача HR", "Создать сильную команду для роста компании"], ["2", "Открытость — это", "Готовность принимать новое и слышать клиентов"], ["3", "Главный в i’way", "Клиент"]];
    a.forEach((r, i) => {
      const y = 2.6 + i * 1.3;
      card(s, MX, y, CW, 1.1, "Ответ " + r[0]);
      circ(s, MX + 0.3, y + 0.22, 0.66, OL, "Номер " + r[0]);
      T(s, r[0], { x: MX + 0.3, y: y + 0.22, w: 0.66, h: 0.66, fontSize: 22, bold: true, color: WHITE, align: "center", valign: "middle" });
      T(s, r[1], { x: MX + 1.4, y, w: 3.3, h: 1.1, fontSize: 15, color: BODY, valign: "middle" });
      T(s, r[2], { x: MX + 4.8, y, w: 6.8, h: 1.1, fontSize: 20, bold: true, color: OL, valign: "middle" });
    });
    s.addNotes("Если ошиблись — не страшно: всё это ещё не раз пригодится.");
  }

  // 26 ============ СПАСИБО
  {
    const s = pres.addSlide({ masterName: "Финал" });
    logoW(s, MX, 0.7, 1.5);
    s.addText("Спасибо!", { placeholder: "title" });
    T(s, "Мы всегда на связи: пиши, звони или заходи — поможем и подскажем.", { x: MX, y: 3.7, w: 5.8, h: 1.2, fontSize: 22, color: WHITE });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: MX, y: 5.3, w: 3.6, h: 0.8, rectRadius: 0.12, fill: { color: MINT }, line: { color: MINT, width: 0 }, objectName: "Почта" });
    T(s, "hr@iway.ru", { x: MX, y: 5.3, w: 3.6, h: 0.8, fontSize: 24, bold: true, color: OL, align: "center", valign: "middle" });
    [["P_t1.png", 7.4, 0.9], ["P_t2.png", 9.95, 2.3], ["P_t3.png", 7.4, 3.7]].forEach(([f, x, y], i) => {
      s.addImage({ path: I(f), x, y, w: 2.3, h: 2.3, objectName: "Портрет " + (i + 1), altText: "Сотрудник HR" });
    });
    s.addNotes("Адрес hr@iway.ru — взят из репозитория HR-портала; проверьте перед показом.");
  }

  // 27–28 ============ QR
  const qr = async (title, sub, qrf, notes, Comp) => {
    const s = pres.addSlide({ masterName: "Контент" });
    await pill(s, "Обратная связь", Comp);
    T(s, title, { x: MX, y: 1.4, w: 6.4, h: 1.9, fontSize: 40, bold: true, color: OL });
    T(s, sub, { x: MX, y: 3.5, w: 5.6, h: 1.2, fontSize: 20, color: BODY });
    card(s, 8.0, 2.3, 4.53, 4.5, "Подложка QR");
    s.addImage({ path: qrf, x: 8.3, y: 2.6, w: 3.93, h: 3.93, objectName: "QR-код", altText: "QR-код" });
    s.addNotes(notes);
  };
  await qr("Поделись обратной связью", "Нам важно твоё мнение — наведи камеру на QR-код", "../src/x/ppt/media/image24.png", "QR-код из исходной презентации.", fa.FaHeart);
  await qr("Оставь оценку", "Это займёт меньше минуты — спасибо!", "../src/x/ppt/media/image25.png", "QR-код из исходной презентации (слайд назывался «Оценка»). Проверьте, куда он ведёт.", fa.FaStar);

  await pres.writeFile({ fileName: "deck.pptx" });
  await applyTheme("deck.pptx", THEME);
  console.log("done");
})();
