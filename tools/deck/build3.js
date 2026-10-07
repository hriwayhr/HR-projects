const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const React = require("react");
const RS = require("react-dom/server");
const fa = require("react-icons/fa");
const { applyTheme } = require(process.env.SKILL + "/scripts/apply_theme.js");

const FONT = "Fedra Sans Pro (Основной текст)";
// корпоративные: зелёный 009634, оливковый 484E41, мятный C9EDDA; акцент: оранжевый FF5A1F
const THEME = {
  name: "iway HR", headFontFace: FONT, bodyFontFace: FONT,
  colors: { dk1: "2B3026", lt1: "FFFFFF", dk2: "484E41", lt2: "F4F4F0", accent1: "009634", accent2: "FF5A1F", accent3: "484E41", accent4: "C9EDDA", accent5: "007026", accent6: "FF8A5B", hlink: "007026", folHlink: "626D5B" },
};
const G = "009634", GD = "007026", G2 = "00AD5A", MINT = "C9EDDA", MINT2 = "E4F1E8";
const OL = "484E41", INK = "2B3026", MUTED = "626D5B", WHITE = "FFFFFF", BG = "F4F4F0", LINE = "D6D8CF";
const OR = "FF5A1F", ORT = "FF8A5B", OLT = "626D5B";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
pres.title = "Отдел HR i’way — знакомство для новых сотрудников";
pres.author = "HR i’way"; pres.company = "i’way";
const C = pres.SchemeColor;
const W = 13.333, H = 7.5, MX = 0.7, CW = W - 2 * MX;
const I = (f) => "img/" + f;

async function icon(Comp, color, px = 256) {
  const svg = RS.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(px) }));
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}
const T = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, valign: "top", ...o });
const tile = (s, x, y, w, h, fill, name, o = {}) => s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: o.r || 0.3, fill: { color: fill }, line: o.border ? { color: o.border, width: 1.25 } : { color: fill, width: 0 }, objectName: name });
const circ = (s, x, y, d, fill, name, border) => s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: border ? { color: border, width: 1.25 } : { color: fill, width: 0 }, objectName: name });
const pill = (s, text, x, y, fill, color, name) => {
  const w = text.length * 0.115 + 0.55;
  tile(s, x, y, w, 0.34, fill, "Тег " + (name || text), { r: 0.17 });
  T(s, text.toUpperCase(), { x, y, w, h: 0.34, fontSize: 10, bold: true, color, charSpacing: 1.5, align: "center", valign: "middle" });
  return w;
};
const logoD = (s, x, y, w) => s.addImage({ path: I("logo.png"), x, y, w, h: w * 785 / 1556, objectName: "Логотип", altText: "i’way" });
const logoW = (s, x, y, w) => s.addImage({ path: I("logo_light.png"), x, y, w, h: w * 206 / 480, objectName: "Логотип", altText: "i’way" });
const arrowCache = {};
async function arrow(s, x, y, d, fill, color, name, border) {
  circ(s, x, y, d, fill, name || "Кнопка", border);
  arrowCache[color] = arrowCache[color] || (await icon(fa.FaArrowRight, color));
  s.addImage({ data: arrowCache[color], x: x + d * 0.28, y: y + d * 0.28, w: d * 0.44, h: d * 0.44, rotate: 315, altText: "" });
}

// ---------- masters
const ttl = (o = {}) => ({ name: "title", type: "title", x: MX, y: 1.0, w: CW, h: 0.8, fontSize: 38, color: C.text1, margin: 0, valign: "top", align: "left", fit: "none", ...o });
const sq = (color) => ({ rect: { x: W - 0.3, y: 0, w: 0.3, h: 0.3, fill: { color } } });
const logoObj = { image: { path: I("logo.png"), x: MX, y: 0.38, w: 0.95, h: 0.95 * 785 / 1556 } };
const sn = { x: W - MX - 0.6, y: 7.0, w: 0.6, h: 0.3, fontSize: 10, color: MUTED, align: "right" };
pres.defineSlideMaster({ title: "Светлый", background: { color: BG }, objects: [logoObj, sq(OR), { placeholder: { options: ttl(), text: "" } }], slideNumber: sn });
pres.defineSlideMaster({ title: "Светлый олива", background: { color: BG }, objects: [logoObj, sq(OL), { placeholder: { options: ttl(), text: "" } }], slideNumber: sn });
const full = (title, bg, tcolor, o) => pres.defineSlideMaster({ title, background: { color: bg }, objects: [{ placeholder: { options: ttl({ color: tcolor, ...o }), text: "" } }] });
full("Титул", BG, C.text1, { x: MX, y: 2.65, w: 6.4, h: 2.3, fontSize: 60 });
full("Раздел олива", OL, C.background1, { x: MX, y: 4.55, w: 7.4, h: 1.1, fontSize: 56 });
full("Раздел оранж", OR, C.background1, { x: MX, y: 4.55, w: 7.4, h: 1.1, fontSize: 56 });
full("Раздел зелёный", G, C.background1, { x: MX, y: 4.55, w: 7.4, h: 1.1, fontSize: 56 });
full("Финал", BG, C.background1, { x: MX + 0.5, y: 2.0, w: 6.2, h: 1.3, fontSize: 72 });
full("Квиз", BG, C.text1, { x: MX, y: 1.0, w: CW, h: 1.6, fontSize: 44 });

(async () => {
  const ico = icon;

  // 1 ============ ТИТУЛ
  {
    const s = pres.addSlide({ masterName: "Титул" });
    logoD(s, MX, 0.6, 1.8);
    pill(s, "Знакомство с отделом HR", MX, 1.95, OR, INK);
    s.addText([
      { text: "Привет!", options: { breakLine: true } },
      { text: "Мы — HR ", options: {} }, { text: "i’way", options: { bold: true, color: G } },
    ], { placeholder: "title" });
    T(s, "Чем занимаемся, как живёт компания и почему здесь классно работать", { x: MX, y: 5.1, w: 5.8, h: 0.9, fontSize: 20, color: MUTED });
    T(s, [{ text: "Юлия Немчинова", options: { bold: true, color: INK, breakLine: true } }, { text: "Руководитель HR-отдела", options: { color: MUTED } }], { x: MX, y: 6.3, w: 5, h: 0.7, fontSize: 16 });
    s.addImage({ path: I("L_hero.png"), x: 7.2, y: 0.6, w: 5.43, h: 4.7, objectName: "Фото", altText: "Девушка на фоне города" });
    tile(s, 7.2, 5.5, 2.6, 1.4, OR, "Плитка приветствия");
    T(s, "Добро пожаловать!", { x: 7.45, y: 5.75, w: 2.1, h: 0.9, fontSize: 22, bold: true, color: INK });
    tile(s, 10.03, 5.5, 2.6, 1.4, G, "Плитка бренда");
    logoW(s, 10.33, 5.85, 1.3);
    await arrow(s, 11.75, 5.65, 0.7, WHITE, G, "Стрелка");
    s.addNotes("Приветствие. За 30 минут познакомимся с отделом HR, культурой i’way и командой.");
  }

  // 2 ============ ПЛАН
  {
    const s = pres.addSlide({ masterName: "Светлый" });
    s.addText("Что нас ждёт.", { placeholder: "title" });
    let x = MX; x += pill(s, "Отдел HR", x, 1.9, MINT, GD) + 0.15; x += pill(s, "Культура i’way", x, 1.9, OR, INK) + 0.15; pill(s, "Команда i’way", x, 1.9, G, WHITE);
    const r = [["1.", "Отдел HR", "Кто мы и как заботимся о тебе на каждом этапе"], ["2.", "Культура i’way", "Миссия, ценности и наши правила игры"], ["3.", "Команда i’way", "Руководство, коллеги и цифры, которыми мы гордимся"]];
    r.forEach((it, i) => {
      const y = 2.9 + i * 1.15;
      s.addShape(pres.shapes.LINE, { x: MX, y, w: CW, h: 0, line: { color: LINE, width: 1 }, objectName: "Линия " + i });
      T(s, it[0], { x: MX, y: y + 0.3, w: 0.7, h: 0.6, fontSize: 28, bold: true, color: i === 1 ? OR : i === 0 ? GD : G, valign: "middle" });
      T(s, it[1], { x: MX + 0.9, y: y + 0.3, w: 4.6, h: 0.6, fontSize: 28, color: INK, valign: "middle" });
      T(s, it[2], { x: 7.0, y: y + 0.3, w: 5.6, h: 0.6, fontSize: 16, color: MUTED, valign: "middle" });
    });
    s.addShape(pres.shapes.LINE, { x: MX, y: 6.35, w: CW, h: 0, line: { color: LINE, width: 1 }, objectName: "Линия 3" });
    tile(s, MX, 6.5, 4.2, 0.45, OR, "Квиз", { r: 0.22 });
    T(s, "В конце — мини-квиз!", { x: MX, y: 6.5, w: 4.2, h: 0.45, fontSize: 14, bold: true, color: INK, align: "center", valign: "middle" });
    s.addNotes("Три блока: HR, культура, команда. В конце — квиз из трёх вопросов.");
  }

  // dividers
  const divider = async (n, title, sub, m, bg, nc, sc, tint) => {
    const s = pres.addSlide({ masterName: m });
    tile(s, 8.2, 0.9, 4.4, 5.7, tint, "Плитка", { r: 0.5 });
    arrowCache["_big" + bg] = arrowCache["_big" + bg] || (await icon(fa.FaArrowRight, bg));
    s.addImage({ data: arrowCache["_big" + bg], x: 9.0, y: 2.4, w: 2.8, h: 2.8, rotate: 315, objectName: "Стрелка", altText: "" });
    T(s, n, { x: MX, y: 0.7, w: 7.4, h: 3.6, fontSize: 230, bold: true, color: nc });
    s.addText(title, { placeholder: "title" });
    T(s, sub, { x: MX, y: 5.7, w: 7.4, h: 0.6, fontSize: 24, color: sc });
    return s;
  };
  await divider("01", "Отдел HR", "Кто мы и чем занимаемся", "Раздел олива", OL, OR, MINT, OLT);

  // 4 ============ ГЛАВНАЯ ЗАДАЧА
  {
    const s = pres.addSlide({ masterName: "Светлый" });
    s.addText("Главная задача отдела HR", { placeholder: "title" });
    tile(s, MX, 2.1, 8.0, 4.6, OL, "Формулировка", { r: 0.4 });
    T(s, [
      { text: "Создать такую экосистему внутри компании, где таланты могут " },
      { text: "раскрываться", options: { bold: true, color: MINT } }, { text: ", а бизнес — " },
      { text: "расти", options: { bold: true, color: ORT } },
      { text: " благодаря слаженной и эффективной работе всей команды." },
    ], { x: MX + 0.5, y: 2.5, w: 7.0, h: 3.8, fontSize: 30, color: WHITE, valign: "middle" });
    tile(s, 8.9, 2.1, 3.73, 2.2, G, "Таланты");
    T(s, "Таланты раскрываются", { x: 9.2, y: 2.4, w: 2.6, h: 1.2, fontSize: 24, bold: true, color: WHITE });
    await arrow(s, 11.6 - 0.1 + 0.1 - 0.0, 3.5, 0.65, WHITE, G);
    tile(s, 8.9, 4.5, 3.73, 2.2, OR, "Бизнес");
    T(s, "Бизнес растёт", { x: 9.2, y: 4.8, w: 2.6, h: 1.2, fontSize: 24, bold: true, color: INK });
    await arrow(s, 11.6, 5.9, 0.65, INK, WHITE);
    s.addNotes("Формулировка главной задачи — без изменений.");
  }

  // 5 ============ КОМАНДА HR
  {
    const s = pres.addSlide({ masterName: "Светлый" });
    s.addText("Знакомьтесь: команда HR", { placeholder: "title" });
    const p = [["L_julia.png", "Юлия Немчинова", "Руководитель отдела HR", MINT, GD], ["L_anna.png", "Анна Шулятицкая", "Ведущий HR-специалист", OR, INK], ["L_elena.png", "Елена Таратынова", "Офис-менеджер", OL, WHITE]];
    const cw = 3.75, gap = (CW - 3 * cw) / 2;
    p.forEach((r, i) => {
      const x = MX + i * (cw + gap);
      s.addImage({ path: I(r[0]), x, y: 2.0, w: cw, h: cw * 3.7 / 3.5, objectName: r[1], altText: r[1] });
      T(s, r[1], { x, y: 6.1, w: cw, h: 0.4, fontSize: 22, color: INK });
      pill(s, r[2], x, 6.55, r[3], r[4]);
    });
    s.addNotes("Представить каждого: роль и зоны ответственности.");
  }

  // 6 ============ EJM
  {
    const s = pres.addSlide({ masterName: "Светлый олива" });
    s.addText("Мы рядом на всём твоём пути", { placeholder: "title" });
    pill(s, "Employee Journey Map", MX, 1.9, MINT, GD);
    const st = [[fa.FaHandshake, "Найм", "Знакомимся и зовём в команду", OR, INK], [fa.FaSeedling, "Адаптация", "Помогаем влиться и освоиться", G, WHITE], [fa.FaHeart, "Вовлечённость", "Чтобы было интересно и тепло", OL, WHITE], [fa.FaGraduationCap, "Обучение", "Делимся знаниями и навыками", MINT, INK], [fa.FaChartLine, "Рост и развитие", "Двигаемся вперёд вместе", WHITE, INK], [fa.FaBullhorn, "HR-бренд", "Рассказываем, какие мы", OR, INK]];
    const cw = 3.85, ch = 2.1, gx = (CW - 3 * cw) / 2;
    for (let i = 0; i < 6; i++) {
      const x = MX + (i % 3) * (cw + gx), y = 2.45 + Math.floor(i / 3) * (ch + 0.2), r = st[i];
      tile(s, x, y, cw, ch, r[3], "Этап " + r[1], { border: r[3] === WHITE ? LINE : null });
      s.addImage({ data: await ico(r[0], r[4] === WHITE ? WHITE : r[4] === INK && r[3] === WHITE ? G : r[4]), x: x + 0.3, y: y + 0.3, w: 0.42, h: 0.42, altText: r[1] });
      T(s, "0" + (i + 1), { x: x + cw - 1.2, y: y + 0.3, w: 0.9, h: 0.4, fontSize: 14, bold: true, color: r[4], align: "right" });
      T(s, r[1], { x: x + 0.3, y: y + 0.95, w: cw - 0.5, h: 0.4, fontSize: 20, bold: true, color: r[4] });
      T(s, r[2], { x: x + 0.3, y: y + 1.4, w: cw - 1.5, h: 0.6, fontSize: 14, color: r[4] });
      await arrow(s, x + cw - 0.9, y + ch - 0.9, 0.62, r[4] === WHITE ? WHITE : r[4], r[3] === WHITE ? WHITE : r[3], "Стрелка " + r[1], r[3] === WHITE ? null : null);
    }
    s.addNotes("Шесть этапов пути сотрудника. Дальше — подробнее про найм, адаптацию и HR-бренд.");
  }

  // 7 ============ НАЙМ
  {
    const s = pres.addSlide({ masterName: "Светлый" });
    s.addText("Найм: как мы собираем команду", { placeholder: "title" });
    pill(s, "EJM · Найм", MX, 1.9, MINT, GD);
    const f = [["Отклики", "5 866", 6.4, MINT, INK], ["Первый контакт", "1 038", 5.6, MINT, INK], ["Приглашение на собеседование", "743", 4.8, WHITE, INK], ["Собеседование", "576", 4.0, WHITE, INK], ["Оффер", "100", 3.2, OL, WHITE], ["Выход", "95", 2.4, G, WHITE]];
    f.forEach((r, i) => {
      const y = 2.5 + i * 0.7;
      tile(s, MX, y, r[2], 0.55, r[3], "Шаг " + r[0], { r: 0.275, border: r[3] === WHITE ? LINE : null });
      T(s, r[0], { x: MX + 0.25, y, w: Math.max(r[2] - 1.5, 2.6), h: 0.55, fontSize: 14, color: r[4], valign: "middle" });
      T(s, r[1], { x: MX + r[2] - 1.3, y, w: 1.05, h: 0.55, fontSize: 18, bold: true, color: r[4], align: "right", valign: "middle" });
    });
    T(s, "*данные на 31.12.2025", { x: MX, y: 6.8, w: 4, h: 0.3, fontSize: 11, color: MUTED });
    tile(s, 7.6, 2.1, 5.03, 3.1, OR, "Выход", { r: 0.4 });
    T(s, "95", { x: 7.95, y: 2.2, w: 3.5, h: 2.0, fontSize: 120, bold: true, color: WHITE });
    T(s, "новых коллег вышли на работу", { x: 7.95, y: 4.2, w: 4.2, h: 0.8, fontSize: 20, bold: true, color: INK });
    await arrow(s, 11.7, 2.35, 0.7, INK, OR);
    tile(s, 7.6, 5.4, 5.03, 1.3, OL, "1 из 60", { r: 0.4 });
    T(s, [{ text: "≈ 1 из 60 ", options: { bold: true, fontSize: 30, color: ORT } }, { text: "откликов становится коллегой", options: { fontSize: 16, color: WHITE } }], { x: 7.95, y: 5.4, w: 4.4, h: 1.3, valign: "middle" });
    s.addNotes("Ширина полос условная. Данные на 31.12.2025.");
  }

  // 8 ============ АДАПТАЦИЯ
  {
    const s = pres.addSlide({ masterName: "Светлый олива" });
    s.addText("Чтобы с первого дня было комфортно", { placeholder: "title" });
    s.addImage({ path: I("L_team.png"), x: MX, y: 2.0, w: 5.2, h: 5.2 * 4.9 / 5.6, objectName: "Фото команды", altText: "Команда за рабочим столом" });
    pill(s, "EJM · Адаптация и развитие", MX, 6.75, MINT, GD);
    const it = [["Welcome-встреча", "Знакомимся и рассказываем, как у нас всё устроено", G, WHITE], ["Неделя адаптации", "Просим короткую анкету: нам важно твоё мнение", OR, INK], ["Обучение", "«Игра по неподачам», «Системный руководитель», «Академия i’way»", OL, WHITE], ["Переводы", "Поддерживаем, если решишь сменить роль или команду", MINT, INK]];
    it.forEach((r, i) => {
      const x = 6.25 + (i % 2) * 3.2, y = 2.0 + Math.floor(i / 2) * 2.45;
      tile(s, x, y, 3.05, 2.3, WHITE, "Шаг " + r[0], { border: LINE });
      circ(s, x + 0.25, y + 0.25, 0.55, r[2], "Номер " + (i + 1));
      T(s, String(i + 1), { x: x + 0.25, y: y + 0.25, w: 0.55, h: 0.55, fontSize: 18, bold: true, color: r[3], align: "center", valign: "middle" });
      T(s, r[0], { x: x + 0.25, y: y + 0.95, w: 2.6, h: 0.35, fontSize: 16, bold: true, color: INK });
      T(s, r[1], { x: x + 0.25, y: y + 1.3, w: 2.6, h: 0.9, fontSize: 12, color: MUTED });
    });
    s.addNotes("Рассказать про welcome-встречу и анкеты. Названия программ оставляем как есть.");
  }

  // 9 ============ HR-БРЕНД
  {
    const s = pres.addSlide({ masterName: "Светлый" });
    s.addText("HR-бренд: как мы о себе рассказываем", { placeholder: "title" });
    const cols = [{ x: MX, fill: MINT, head: "Снаружи", col: INK, hc: GD, items: ["Карьерные сайты: hh.ru и LinkedIn", "Наружная реклама: метро и экраны", "Работа с университетами", "Ответы на отзывы на площадках"] }, { x: MX + 6.1, fill: OL, head: "Внутри", col: WHITE, hc: ORT, items: ["Миссия и ценности", "Внутренние коммуникации", "Мотивация и бенефиты", "EVP — уникальное ценностное предложение"] }];
    for (const c of cols) {
      tile(s, c.x, 2.1, 5.8, 4.6, c.fill, "Колонка " + c.head, { r: 0.4 });
      T(s, c.head, { x: c.x + 0.45, y: 2.4, w: 3.5, h: 0.9, fontSize: 40, bold: true, color: c.hc });
      c.items.forEach((t, i) => {
        const y = 3.55 + i * 0.75;
        s.addShape(pres.shapes.LINE, { x: c.x + 0.45, y: y - 0.1, w: 4.9, h: 0, line: { color: c.fill === MINT ? "A9D9BF" : OLT, width: 1 }, objectName: "Линия" });
        T(s, t, { x: c.x + 0.45, y, w: 4.9, h: 0.6, fontSize: 17, color: c.col, valign: "middle" });
      });
      await arrow(s, c.x + 5.8 - 1.0, 2.4, 0.65, c.fill === MINT ? OR : OR, INK);
    }
    s.addNotes("Снаружи — как нас видят кандидаты, внутри — как мы живём.");
  }

  await divider("02", "Культура i’way", "Во что мы верим и как работаем вместе", "Раздел оранж", OR, WHITE, INK, ORT);

  // 11 ============ О КОМПАНИИ
  {
    const s = pres.addSlide({ masterName: "Светлый" });
    s.addText("i’way — трансферы по всему миру", { placeholder: "title" });
    tile(s, MX, 2.0, 4.6, 4.8, G, "Страны", { r: 0.4 });
    T(s, "130+", { x: MX + 0.4, y: 2.3, w: 4.0, h: 2.2, fontSize: 110, bold: true, color: WHITE });
    T(s, "стран, где мы возим людей", { x: MX + 0.4, y: 4.6, w: 3.5, h: 1.0, fontSize: 22, bold: true, color: WHITE });
    await arrow(s, MX + 4.6 - 1.0, 2.0 + 4.8 - 0.95, 0.65, WHITE, G);
    tile(s, 5.5, 2.0, 3.6, 2.3, OL, "Поездки", { r: 0.4 });
    T(s, "2 500+", { x: 5.85, y: 2.3, w: 3.0, h: 1.0, fontSize: 48, bold: true, color: WHITE });
    T(s, "поездок ежедневно", { x: 5.85, y: 3.5, w: 3.0, h: 0.5, fontSize: 18, color: WHITE });
    tile(s, 5.5, 4.5, 3.6, 2.3, OR, "Аэропорты", { r: 0.4 });
    T(s, "600+", { x: 5.85, y: 4.8, w: 3.0, h: 1.0, fontSize: 48, bold: true, color: INK });
    T(s, "аэропортов мира", { x: 5.85, y: 6.0, w: 3.0, h: 0.5, fontSize: 18, color: INK });
    [["с 2009", "года на рынке", MINT, GD], ["4,9 из 5", "оценка поездок", WHITE, GD], ["Офисы", "в Казахстане, ОАЭ, Индии", WHITE, GD]].forEach((r, i) => {
      const y = 2.0 + i * 1.65;
      tile(s, 9.3, y, 3.33, 1.5, r[2], "Факт " + r[0], { r: 0.4, border: r[2] === WHITE ? LINE : null });
      T(s, r[0], { x: 9.65, y: y + 0.2, w: 2.8, h: 0.6, fontSize: 28, bold: true, color: r[3] });
      T(s, r[1], { x: 9.65, y: y + 0.85, w: 2.8, h: 0.5, fontSize: 14, color: INK });
    });
    s.addNotes("130+ стран, 2 500+ поездок и 600+ аэропортов — из внутренней презентации. Оценка 4,9, офисы в Казахстане, ОАЭ и Индии — по данным Felo-поиска (App Store, блог i’way, Forbes.kz); проверьте актуальность.");
  }

  // 12 ============ ДАШБОРД
  {
    const s = pres.addSlide({ masterName: "Светлый олива" });
    s.addText("Наш день в цифрах", { placeholder: "title" });
    T(s, "Бронирования, выручка и оценки клиентов — всё на одном экране, в реальном времени.", { x: MX, y: 2.2, w: 4.2, h: 1.9, fontSize: 22, color: INK });
    T(s, "Каждый из нас влияет на эти цифры.", { x: MX, y: 4.3, w: 4.0, h: 0.8, fontSize: 16, color: MUTED });
    s.addImage({ path: I("R_dash.png"), x: W - MX - 7.4, y: 2.0, w: 7.4, h: 4.18, objectName: "Дашборд", altText: "Панель с онлайн-метриками" });
    tile(s, W - MX - 7.4 - 0.6, 5.7, 2.4, 1.3, OR, "Оценка", { r: 0.35 });
    T(s, "4,9 из 5", { x: W - MX - 7.4 - 0.35, y: 5.85, w: 2.2, h: 0.6, fontSize: 28, bold: true, color: INK });
    T(s, "оценка поездок", { x: W - MX - 7.4 - 0.35, y: 6.45, w: 2.2, h: 0.4, fontSize: 14, color: INK });
    s.addNotes("Скриншот внутреннего дашборда. Перед показом широкой аудитории проверьте конфиденциальность цифр.");
  }

  // 13 ============ ИСТОРИЯ
  {
    const s = pres.addSlide({ masterName: "Светлый" });
    s.addText("Как всё начиналось", { placeholder: "title" });
    s.addImage({ path: I("L_found.png"), x: MX, y: 2.05, w: 3.3, h: 4.5, objectName: "Основатели", altText: "Основатели i’way" });
    const ev = [["2009", "ООО «Сибирская трансферная компания»", MINT, GD, INK, 3.0], ["2011", "iWay Express: двуязычный сайт с онлайн-бронированием", WHITE, G, INK, 3.5], ["2013", "Родился бренд i’way", OL, ORT, WHITE, 4.0], ["2023", "Открыли офис в Казахстане", OR, WHITE, INK, 4.5]];
    const cw = 2.0, gap = 0.17, x0 = 4.45;
    ev.forEach((r, i) => {
      const x = x0 + i * (cw + gap), h = r[5], y = 6.65 - h;
      tile(s, x, y, cw, h, r[2], "Год " + r[0], { r: 0.35, border: r[2] === WHITE ? LINE : null });
      T(s, r[0], { x: x + 0.25, y: y + 0.3, w: cw - 0.4, h: 0.7, fontSize: 34, bold: true, color: r[3] });
      T(s, r[1], { x: x + 0.25, y: y + 1.1, w: cw - 0.45, h: 1.8, fontSize: 14, color: r[4] });
    });
    s.addNotes("Даты 2009–2013 — из внутренней презентации; офис в Казахстане (начало 2023, Алматы) — Forbes.kz, по данным Felo-поиска.");
  }

  // 14 ============ МИССИЯ
  {
    const s = pres.addSlide({ masterName: "Светлый" });
    s.addText("Миссия", { placeholder: "title" });
    tile(s, MX, 1.95, CW, 4.85, OL, "Миссия", { r: 0.5 });
    T(s, "i’way меняет представление о транспортном сервисе в России и мире и, ориентируясь на потребности клиентов, выступает законодателем стандартов обслуживания.", { x: MX + 0.7, y: 2.4, w: 9.6, h: 3.5, fontSize: 34, color: WHITE, valign: "middle" });
    logoW(s, MX + 0.7, 6.0, 0.9);
    circ(s, W - MX - 1.9, 5.1, 1.4, OR, "Круг");
    await arrow(s, W - MX - 1.55, 5.45, 0.7, OR, INK);
    s.addNotes("Миссия — формулировка без изменений.");
  }

  // 15 ============ ЦЕННОСТИ
  {
    const s = pres.addSlide({ masterName: "Светлый олива" });
    s.addText("Наши ценности", { placeholder: "title" });
    pill(s, "Бренд-код", MX, 1.9, MINT, GD);
    const v = [
      ["Открытость", "Готовность принимать новое, прислушиваться к просьбам и проблемам клиентов; старание быть нужным.", OL, WHITE, ORT, 0, 0, 3.85, 4.4],
      ["Честность", "Соблюдение делового этикета и корпоративной политики; неприятие обмана и хитростей в корыстных целях.", MINT, INK, GD, 1, 0, 3.85, 2.1],
      ["Лидерство", "Предоставление клиентам лучшего; ввод новых стандартов обслуживания.", OR, INK, INK, 1, 1, 3.85, 2.1],
      ["Технологичность", "Внедрение современных решений.", WHITE, INK, G, 2, 0, 3.85, 2.1],
      ["Человечность", "Уважительное отношение; дружелюбие в общении.", GD, WHITE, MINT, 2, 1, 3.85, 2.1],
    ];
    const colx = [MX, MX + 4.025, MX + 8.05];
    for (const r of v) {
      const x = colx[r[5]], y = 2.4 + r[6] * 2.3, big = r[8] > 3;
      tile(s, x, y, r[7], r[8], r[2], "Ценность " + r[0], { r: 0.35, border: r[2] === WHITE ? LINE : null });
      T(s, r[0], { x: x + 0.3, y: y + (big ? 1.0 : 0.25), w: big ? r[7] - 0.6 : r[7] - 1.3, h: 0.5, fontSize: big ? 32 : 20, bold: true, color: r[4] });
      T(s, r[1], { x: x + 0.3, y: y + (big ? 1.8 : 0.8), w: r[7] - 0.6, h: big ? 2.3 : 1.2, fontSize: big ? 18 : 14, color: r[3] });
      await arrow(s, x + r[7] - 0.8, y + 0.2, 0.55, r[2] === OR ? INK : (r[2] === WHITE ? OR : (r[2] === MINT ? G : WHITE)), r[2] === OR ? OR : (r[2] === WHITE || r[2] === MINT ? WHITE : r[2]));
    }
    s.addNotes("Ценности — формулировки из бренд-кода, без изменений.");
  }

  // 16 ============ КАК У НАС ПРИНЯТО
  {
    const s = pres.addSlide({ masterName: "Светлый" });
    s.addText("Как у нас принято", { placeholder: "title" });
    pill(s, "Культура i’way", MX, 1.9, OR, INK);
    const r = [[fa.FaTshirt, "Дресс-код", "Smart Casual: выглядим опрятно и остаёмся собой", MINT, INK, GD], [fa.FaUserFriends, "Руководитель рядом", "Первая точка входа для любого вопроса", OL, WHITE, ORT], [fa.FaShieldAlt, "Ответственность", "Отвечаем за результат и держим слово", OR, INK, INK], [fa.FaLightbulb, "Идеи приветствуются", "Предложил полезное — поможем воплотить", WHITE, INK, G], [fa.FaHeart, "Неравнодушие", "Нам не всё равно — к клиентам и друг к другу", GD, WHITE, MINT]];
    const pos = [[MX, 2.5, 3.85], [MX + 4.025, 2.5, 3.85], [MX + 8.05, 2.5, 3.85], [MX, 4.75, 5.9], [MX + 6.1, 4.75, 5.8]];
    for (let i = 0; i < 5; i++) {
      const [x, y, w] = pos[i], q = r[i];
      tile(s, x, y, w, 2.05, q[3], "Правило " + q[1], { border: q[3] === WHITE ? LINE : null });
      s.addImage({ data: await ico(q[0], q[5]), x: x + 0.3, y: y + 0.3, w: 0.45, h: 0.45, altText: q[1] });
      T(s, q[1], { x: x + 0.3, y: y + 0.95, w: w - 0.5, h: 0.4, fontSize: 19, bold: true, color: q[4] });
      T(s, q[2], { x: x + 0.3, y: y + 1.4, w: w - 0.6, h: 0.55, fontSize: 14, color: q[4] });
    }
    s.addNotes("Пять принципов корпоративной культуры из внутренней презентации, переформулированы дружелюбнее.");
  }

  // 17 ============ АПОСТРОФ
  {
    const s = pres.addSlide({ masterName: "Светлый олива" });
    s.addText("Наш апостроф — особенный", { placeholder: "title" });
    tile(s, MX, 2.1, 5.3, 4.6, WHITE, "Плитка логотипа", { r: 0.4, border: LINE });
    logoD(s, MX + 0.7, 3.0, 3.9);
    const rows = [["i’way", true, "Правильно — с красивым апострофом", G, WHITE], ["i'way", false, "Не так — прямой апостроф", WHITE, MUTED], ["i`way", false, "И не так — обратный апостроф", WHITE, MUTED]];
    for (let i = 0; i < 3; i++) {
      const r = rows[i], y = 2.1 + i * 1.35;
      tile(s, 6.3, y, 6.33, 1.2, r[3], "Вариант " + r[0], { r: 0.35, border: r[3] === WHITE ? LINE : null });
      T(s, r[0], { x: 6.65, y, w: 2.6, h: 1.2, fontSize: r[1] ? 44 : 34, bold: true, color: r[4], valign: "middle" });
      T(s, r[2], { x: 9.2, y, w: 2.6, h: 1.2, fontSize: 14, color: r[1] ? WHITE : MUTED, valign: "middle" });
      circ(s, 11.85, y + 0.3, 0.6, r[1] ? WHITE : MUTED, r[1] ? "Верно" : "Неверно");
      s.addImage({ data: await ico(r[1] ? fa.FaCheck : fa.FaTimes, r[1] ? G : WHITE), x: 12.02, y: y + 0.47, w: 0.26, h: 0.26, altText: r[1] ? "верно" : "неверно" });
    }
    T(s, "Как напечатать на Windows:", { x: 6.3, y: 6.2, w: 3.0, h: 0.5, fontSize: 15, color: INK, valign: "middle" });
    [["Alt", 9.5, 0.9], ["+", 10.45, 0.35], ["0146", 10.85, 1.3]].forEach(([t, x, w]) => {
      if (t === "+") { T(s, t, { x, y: 6.2, w, h: 0.5, fontSize: 22, bold: true, color: OR, align: "center", valign: "middle" }); return; }
      tile(s, x, 6.2, w, 0.5, OR, "Клавиша " + t, { r: 0.12 });
      T(s, t, { x, y: 6.2, w, h: 0.5, fontSize: 18, bold: true, color: INK, align: "center", valign: "middle" });
    });
    s.addNotes("Пишем i’way с типографским апострофом (Alt+0146).");
  }

  await divider("03", "Команда i’way", "Люди, благодаря которым всё работает", "Раздел зелёный", G, MINT, WHITE, G2);

  // 19 ============ ДИРЕКЦИЯ
  {
    const s = pres.addSlide({ masterName: "Светлый" });
    s.addText("Дирекция i’way", { placeholder: "title" });
    const d = [["R_d1.png", "Дмитрий Салихов", "CEO, основатель i’way", OL, WHITE], ["R_d2.png", "Дмитрий Сарайкин", "Сооснователь i’way", OR, INK], ["R_d3.png", "Александр Шведов", "CTO, исполнительный директор", MINT, INK], ["R_d5.png", "Джехад Абугсиса", "Директор по международному развитию", GD, WHITE]];
    const cw = 2.85, gap = (CW - 4 * cw) / 3;
    d.forEach((p, i) => {
      const x = MX + i * (cw + gap);
      s.addImage({ path: I(p[0]), x, y: 2.0, w: cw, h: 4.0, objectName: p[1], altText: p[1] });
      tile(s, x, 6.1, cw, 0.95, p[3], "Подпись " + p[1], { r: 0.25 });
      T(s, p[1], { x: x + 0.2, y: 6.18, w: cw - 0.4, h: 0.35, fontSize: 15, bold: true, color: p[4] });
      T(s, p[2], { x: x + 0.2, y: 6.53, w: cw - 0.4, h: 0.5, fontSize: 11, color: p[4] });
    });
    s.addNotes("Слайд Ольги Чикан (операционный директор) был скрыт в исходной презентации, поэтому здесь её нет.");
  }

  // 20 ============ ЦИФРЫ КОМАНДЫ
  {
    const s = pres.addSlide({ masterName: "Светлый олива" });
    s.addText("Мы — команда", { placeholder: "title" });
    tile(s, MX, 2.0, 6.4, 4.8, OL, "Сотрудники", { r: 0.45 });
    T(s, "160+", { x: MX + 0.5, y: 2.4, w: 5.5, h: 2.5, fontSize: 140, bold: true, color: WHITE });
    T(s, "коллег в команде i’way", { x: MX + 0.5, y: 5.2, w: 5.2, h: 0.6, fontSize: 24, bold: true, color: ORT });
    const st = [[fa.FaFemale, "100+", "девушек", OR, INK], [fa.FaMale, "50+", "парней", MINT, INK], [fa.FaBirthdayCake, "32", "года — средний возраст", G, WHITE]];
    for (let i = 0; i < 3; i++) {
      const y = 2.0 + i * 1.65, r = st[i];
      tile(s, 7.3, y, 5.33, 1.5, r[3], "Плитка " + r[2], { r: 0.4 });
      s.addImage({ data: await ico(r[0], r[4]), x: 7.65, y: y + 0.5, w: 0.5, h: 0.5, altText: r[2] });
      T(s, r[1], { x: 8.5, y: y + 0.15, w: 2.0, h: 0.8, fontSize: 44, bold: true, color: r[4], valign: "middle" });
      T(s, r[2], { x: 8.5, y: y + 0.95, w: 3.4, h: 0.4, fontSize: 16, color: r[4] });
      await arrow(s, 11.7, y + 0.4, 0.7, r[4], r[3]);
    }
    s.addNotes("Данные из внутренней презентации.");
  }

  // 21 ============ КАРТА
  {
    const s = pres.addSlide({ masterName: "Светлый" });
    s.addText("Где нас можно встретить", { placeholder: "title" });
    tile(s, MX, 2.1, 2.9, 4.8, MINT, "Подпись", { r: 0.4 });
    T(s, "Города России и страны, где работает i’way", { x: MX + 0.3, y: 2.4, w: 2.4, h: 1.9, fontSize: 18, bold: true, color: GD });
    T(s, "Мы всё ближе к клиентам и партнёрам по всему миру", { x: MX + 0.3, y: 4.5, w: 2.4, h: 1.6, fontSize: 14, color: INK });
    s.addImage({ path: I("map.png"), x: W - MX - 8.9 + 0.0, y: 2.1, w: 8.9, h: 4.8, objectName: "Карта", altText: "Карта присутствия i’way" });
    s.addNotes("Города России и страны присутствия — по карте.");
  }

  // 22–24 ============ КВИЗ
  const quiz = (n, q, A, B, right, note, ca, cb) => {
    const s = pres.addSlide({ masterName: "Квиз" });
    pill(s, `Мини-квиз · вопрос ${n} из 3`, MX, 0.5, OR, INK);
    s.addText(q, { placeholder: "title" });
    [[A, ca], [B, cb]].forEach(([t, c], i) => {
      const x = MX + i * 6.1;
      tile(s, x, 3.2, 5.8, 3.3, c[0], "Вариант " + "AB"[i], { r: 0.45 });
      circ(s, x + 0.4, 3.6, 0.8, c[1], "Буква " + "AB"[i]);
      T(s, "AB"[i], { x: x + 0.4, y: 3.6, w: 0.8, h: 0.8, fontSize: 28, bold: true, color: c[0], align: "center", valign: "middle" });
      T(s, t, { x: x + 0.4, y: 4.6, w: 5.0, h: 1.7, fontSize: 22, bold: true, color: c[2], valign: "top" });
    });
    s.addNotes("Правильный ответ: " + "AB"[right] + ". " + note);
  };
  quiz(1, "Какая главная задача отдела HR в i’way?", "Укомплектованность штата", "Создать сильную команду для роста компании", 1, "Создать сильную команду для роста компании.", [OR, INK, INK], [OL, WHITE, WHITE]);
  quiz(2, "Ценность «открытость» — это…", "Готовность принимать новое и прислушиваться к потребностям клиентов", "Принцип «открытых дверей»: с идеей можно прийти к руководителю", 0, "Готовность принимать новое и прислушиваться к потребностям клиентов.", [OL, WHITE, WHITE], [MINT, GD, INK]);
  quiz(3, "Кто в i’way главный?", "Клиент", "CEO", 0, "Клиент.", [G, WHITE, WHITE], [OR, INK, INK]);

  // 25 ============ ОТВЕТЫ
  {
    const s = pres.addSlide({ masterName: "Светлый" });
    s.addText("Проверяем себя", { placeholder: "title" });
    const a = [["1", "Главная задача HR", "Создать сильную команду для роста компании", OR, INK], ["2", "Открытость — это", "Готовность принимать новое и слышать клиентов", OL, WHITE], ["3", "Главный в i’way", "Клиент", G, WHITE]];
    a.forEach((r, i) => {
      const y = 2.1 + i * 1.5;
      tile(s, MX, y, CW, 1.3, WHITE, "Ответ " + r[0], { r: 0.4, border: LINE });
      circ(s, MX + 0.3, y + 0.25, 0.8, r[3], "Номер " + r[0]);
      T(s, r[0], { x: MX + 0.3, y: y + 0.25, w: 0.8, h: 0.8, fontSize: 28, bold: true, color: r[4], align: "center", valign: "middle" });
      T(s, r[1], { x: MX + 1.5, y, w: 3.2, h: 1.3, fontSize: 16, color: MUTED, valign: "middle" });
      T(s, r[2], { x: MX + 4.9, y, w: 6.8, h: 1.3, fontSize: 22, bold: true, color: INK, valign: "middle" });
    });
    s.addNotes("Если ошиблись — не страшно: всё это ещё не раз пригодится.");
  }

  // 26 ============ СПАСИБО
  {
    const s = pres.addSlide({ masterName: "Финал" });
    tile(s, MX, 0.7, 6.9, 6.1, OL, "Плитка", { r: 0.5 });
    logoW(s, MX + 0.5, 1.0, 1.3);
    s.addText("Спасибо!", { placeholder: "title" });
    T(s, "Мы всегда на связи: пиши, звони или заходи — поможем и подскажем.", { x: MX + 0.5, y: 3.4, w: 5.5, h: 1.2, fontSize: 22, color: WHITE });
    tile(s, MX + 0.5, 5.4, 3.6, 0.85, OR, "Почта", { r: 0.42 });
    T(s, "hr@iway.ru", { x: MX + 0.5, y: 5.4, w: 3.6, h: 0.85, fontSize: 26, bold: true, color: INK, align: "center", valign: "middle" });
    [["L_julia.png", 8.0, 0.7, MINT], ["L_anna.png", 10.4, 2.3, OR], ["L_elena.png", 8.0, 3.9, G]].forEach(([f, x, y], i) => {
      s.addImage({ path: I(f), x, y, w: 2.2, h: 2.2 * 3.7 / 3.5, objectName: "Портрет " + (i + 1), altText: "Сотрудник HR" });
    });
    s.addNotes("Адрес hr@iway.ru — взят из репозитория HR-портала; проверьте перед показом.");
  }

  // 27–28 ============ QR
  const qr = (title, sub, qrf, notes, c) => {
    const s = pres.addSlide({ masterName: "Светлый" });
    tile(s, MX, 1.4, 7.2, 5.4, c, "Плитка", { r: 0.5 });
    T(s, title, { x: MX + 0.6, y: 1.9, w: 6.0, h: 2.6, fontSize: 48, bold: true, color: WHITE });
    T(s, sub, { x: MX + 0.6, y: 4.9, w: 5.6, h: 1.2, fontSize: 20, color: WHITE });
    tile(s, 8.3, 1.4, 4.33, 5.4, WHITE, "Подложка QR", { r: 0.5, border: LINE });
    s.addImage({ path: qrf, x: 8.5, y: 2.1, w: 3.93, h: 3.93, objectName: "QR-код", altText: "QR-код" });
    s.addNotes(notes);
  };
  qr("Поделись обратной связью", "Нам важно твоё мнение — наведи камеру на QR-код", "../src/x/ppt/media/image24.png", "QR-код из исходной презентации.", OL);
  qr("Оставь оценку", "Это займёт меньше минуты — спасибо!", "../src/x/ppt/media/image25.png", "QR-код из исходной презентации (слайд назывался «Оценка»). Проверьте, куда он ведёт.", GD);

  await pres.writeFile({ fileName: "deck.pptx" });
  await applyTheme("deck.pptx", THEME);
  console.log("done");
})();
