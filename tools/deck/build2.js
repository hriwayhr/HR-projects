const pptxgen = require("pptxgenjs");
const sharp = require("sharp");
const React = require("react");
const RS = require("react-dom/server");
const fa = require("react-icons/fa");
const { applyTheme } = require(process.env.SKILL + "/scripts/apply_theme.js");

const FONT = "Fedra Sans Pro (Основной текст)";
const THEME = {
  name: "iway HR", headFontFace: FONT, bodyFontFace: FONT,
  colors: { dk1: "484E41", lt1: "FFFFFF", dk2: "007026", lt2: "E4F1E8", accent1: "009634", accent2: "00AD5A", accent3: "4DC68C", accent4: "99DEBD", accent5: "C9EDDA", accent6: "626D5B", hlink: "007026", folHlink: "626D5B" },
};
const G = "009634", GD = "007026", G2 = "00AD5A", MINT = "C9EDDA", MINT2 = "E4F1E8", MINT3 = "99DEBD", OL = "484E41", MUTED = "626D5B", WHITE = "FFFFFF";

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";
pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
pres.title = "Отдел HR i’way — знакомство для новых сотрудников";
pres.author = "HR i’way"; pres.company = "i’way";
const C = pres.SchemeColor;
const W = 13.333, H = 7.5, MX = 0.7;
const I = (f) => "img/" + f;
const CR = 1336 / 1056; // comma h/w

async function icon(Comp, color, px = 256) {
  const svg = RS.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(px) }));
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}
const T = (s, text, o) => s.addText(text, { isTextBox: true, margin: 0, valign: "top", ...o });
const rect = (s, x, y, w, h, fill, name, r) => s.addShape(r ? pres.shapes.ROUNDED_RECTANGLE : pres.shapes.RECTANGLE, { x, y, w, h, rectRadius: r || undefined, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: name });
const circle = (s, x, y, d, fill, name) => s.addShape(pres.shapes.OVAL, { x, y, w: d, h: d, fill: { color: fill }, line: { color: fill, width: 0 }, objectName: name });
const comma = (s, f, x, y, w, name) => s.addImage({ path: I(f), x, y, w, h: w * CR, objectName: name || "Апостроф", altText: "" });
const chip = (s, text, x, y, fill = MINT, color = GD) => {
  const w = text.length * 0.15 + 0.7;
  rect(s, x, y, w, 0.42, fill, "Метка " + text, 0.21);
  T(s, text.toUpperCase(), { x, y, w, h: 0.42, fontSize: 12, bold: true, color, charSpacing: 3, align: "center", valign: "middle" });
  return w;
};
const logoW = (s, x, y, w) => s.addImage({ path: I("logo_light.png"), x, y, w, h: w * 206 / 480, objectName: "Логотип", altText: "i’way" });
const logoD = (s, x, y, w) => s.addImage({ path: I("logo.png"), x, y, w, h: w * 785 / 1556, objectName: "Логотип", altText: "i’way" });

// ---------- masters
const ttl = (color, o = {}) => ({ name: "title", type: "title", x: MX, y: 0.85, w: 11.9, h: 0.9, fontSize: 40, bold: true, color, margin: 0, valign: "top", align: "left", fit: "none", ...o });
const foot = (c) => [
  { image: { path: I(c === "w" ? "comma_white.png" : "comma_g.png"), x: MX, y: 6.95, w: 0.2, h: 0.2 * CR } },
  { text: { text: "HR i’way", options: { x: MX + 0.3, y: 6.93, w: 2, h: 0.3, fontSize: 10, color: c === "w" ? WHITE : MUTED, margin: 0, valign: "middle" } } },
];
const num = (c) => ({ x: W - MX - 0.6, y: 6.93, w: 0.6, h: 0.3, fontSize: 10, color: c, align: "right" });
const master = (title, bg, tcolor, tOpts, fcol) => pres.defineSlideMaster({
  title, background: { color: bg },
  objects: [...(fcol ? foot(fcol) : []), { placeholder: { options: ttl(tcolor, tOpts), text: "" } }],
  ...(fcol ? { slideNumber: num(fcol === "w" ? WHITE : MUTED) } : {}),
});
master("Белый", WHITE, C.text1, {}, "d");
master("Мятный", MINT2, C.text1, {}, "d");
master("Зелёный", G, C.background1, {}, "w");
master("Глубокий", GD, C.background1, {}, "w");
master("Титул", G, C.background1, { x: MX, y: 2.5, w: 6.4, h: 2.3, fontSize: 54 });
master("Узкий", WHITE, C.text1, { w: 5.6, h: 1.2, fontSize: 32 }, "d");
master("Фото слева", WHITE, C.text1, { x: 7.0, w: 5.6, h: 1.6, fontSize: 34 }, "d");
master("Раздельный", G, C.background1, {});
master("Левая колонка", G, C.background1, { x: MX, y: 2.6, w: 4.4, h: 2.4, fontSize: 54 }, "w");
master("Раздел зелёный", G, C.background1, { x: MX, y: 4.4, w: 9, h: 1.1, fontSize: 60 });
master("Раздел глубокий", GD, C.background1, { x: MX, y: 4.4, w: 9, h: 1.1, fontSize: 60 });
master("Раздел мятный", MINT, C.text1, { x: MX, y: 4.4, w: 9, h: 1.1, fontSize: 60 });
master("Финал", G, C.background1, { x: MX, y: 2.2, w: 8, h: 2.0, fontSize: 96 });
master("QR", G, C.background1, { x: MX, y: 1.5, w: 6.8, h: 2.8, fontSize: 52 });
master("QR глубокий", GD, C.background1, { x: MX, y: 1.5, w: 6.8, h: 2.8, fontSize: 52 });
master("Вопрос", G, C.background1, { x: MX, y: 1.5, w: 11.9, h: 1.6, fontSize: 48 });
master("Вопрос глубокий", GD, C.background1, { x: MX, y: 1.5, w: 11.9, h: 1.6, fontSize: 48 });

(async () => {
  const ico = (c, col) => icon(c, col);

  // 1 ================= ТИТУЛ
  {
    const s = pres.addSlide({ masterName: "Титул" });
    s.addImage({ path: I("c_hero.png"), x: W - 6.0 - 0.2, y: 0.1, w: 6.0, h: 7.6, objectName: "Фото в форме апострофа", altText: "Девушка на фоне города" });
    comma(s, "comma_green.png", 6.6, 5.7, 1.6, "Акцент");
    logoW(s, MX, 0.65, 1.6);
    chip(s, "Знакомство с отделом HR", MX, 1.8, WHITE, GD);
    s.addText("Привет!\nМы — HR i’way", { placeholder: "title" });
    T(s, "Чем занимаемся, как живёт компания и почему здесь классно работать", { x: MX, y: 5.0, w: 6.0, h: 0.9, fontSize: 20, color: WHITE });
    T(s, [{ text: "Юлия Немчинова", options: { bold: true, breakLine: true } }, { text: "Руководитель HR-отдела" }], { x: MX, y: 6.4, w: 5, h: 0.7, fontSize: 16, color: WHITE });
    s.addNotes("Приветствие. За 30 минут познакомимся с отделом HR, культурой i’way и командой.");
  }

  // 2 ================= ПЛАН
  {
    const s = pres.addSlide({ masterName: "Мятный" });
    chip(s, "План встречи", MX, 0.35);
    s.addText("Что нас ждёт", { placeholder: "title" });
    const c = [[G, WHITE, WHITE, "01", "Отдел HR", "Кто мы и как заботимся о тебе на каждом этапе"], [MINT, OL, GD, "02", "Культура i’way", "Миссия, ценности и наши правила игры"], [GD, WHITE, MINT, "03", "Команда i’way", "Руководство, коллеги и цифры, которыми мы гордимся"]];
    const cw = 3.85, gap = (W - 2 * MX - 3 * cw) / 2;
    c.forEach((r, i) => {
      const x = MX + i * (cw + gap), y = 2.0 + (i === 1 ? 0.3 : 0);
      rect(s, x, y, cw, 4.0, r[0], "Блок " + r[3], 0.35);
      T(s, r[3], { x: x + 0.4, y: y + 0.25, w: cw - 0.8, h: 1.5, fontSize: 88, bold: true, color: r[2] });
      T(s, r[4], { x: x + 0.4, y: y + 2.05, w: cw - 0.8, h: 0.55, fontSize: 26, bold: true, color: r[1] });
      T(s, r[5], { x: x + 0.4, y: y + 2.75, w: cw - 0.8, h: 1.3, fontSize: 16, color: r[1] });
    });
    T(s, "В конце — мини-квиз: проверим, что запомнилось", { x: MX, y: 6.55, w: 8, h: 0.3, fontSize: 13, bold: true, color: GD });
    s.addNotes("Три блока: HR, культура, команда. В конце — квиз из трёх вопросов.");
  }

  // dividers
  const divider = (n, title, sub, master, nc, tc, bgc) => {
    const s = pres.addSlide({ masterName: master });
    comma(s, bgc, 8.2, -1.6, 7.2, "Апостроф");
    T(s, n, { x: MX, y: 0.7, w: 8, h: 3.6, fontSize: 230, bold: true, color: nc });
    s.addText(title, { placeholder: "title" });
    T(s, sub, { x: MX, y: 5.65, w: 8, h: 0.6, fontSize: 24, color: tc });
    return s;
  };
  divider("01", "Отдел HR", "Кто мы и чем занимаемся", "Раздел зелёный", MINT, WHITE, "comma_mint.png").addNotes("Блок 1.");

  // 4 ================= ЗАЧЕМ МЫ ЗДЕСЬ
  {
    const s = pres.addSlide({ masterName: "Мятный" });
    comma(s, "comma_mint.png", 9.4, 2.4, 5.4, "Апостроф");
    chip(s, "Отдел HR", MX, 0.35);
    s.addText("Главная задача отдела HR", { placeholder: "title" });
    T(s, [
      { text: "Создать такую экосистему внутри компании, где таланты могут " },
      { text: "раскрываться", options: { bold: true, color: G } },
      { text: ", а бизнес — " },
      { text: "расти", options: { bold: true, color: G } },
      { text: " благодаря слаженной и эффективной работе всей команды." },
    ], { x: MX, y: 2.1, w: 9.2, h: 4.2, fontSize: 36, bold: true, color: OL, paraSpaceAfter: 6 });
    s.addNotes("Формулировка главной задачи — без изменений.");
  }

  // 5 ================= КОМАНДА HR
  {
    const s = pres.addSlide({ masterName: "Белый" });
    chip(s, "Отдел HR", MX, 0.35);
    s.addText("Знакомьтесь: команда HR", { placeholder: "title" });
    const p = [["c_julia.png", "Юлия Немчинова", "Руководитель отдела HR", 2.15], ["c_anna.png", "Анна Шулятицкая", "Ведущий HR-специалист", 1.8], ["c_elena.png", "Елена Таратынова", "Офис-менеджер", 2.15]];
    const cw = 3.0, gap = (W - 2 * MX - 3 * cw) / 2;
    p.forEach((r, i) => {
      const x = MX + i * (cw + gap), y = r[3] - (i === 1 ? 0 : 0.0);
      s.addImage({ path: I(r[0]), x, y, w: cw, h: cw * 4.17 / 3.3, objectName: r[1], altText: r[1] });
      T(s, r[1], { x, y: y + 3.85, w: cw + 0.4, h: 0.4, fontSize: 22, bold: true, color: C.text1 });
      T(s, r[2], { x, y: y + 4.27, w: cw + 0.4, h: 0.3, fontSize: 15, color: GD, bold: true });
    });
    s.addNotes("Представить каждого: роль и зоны ответственности.");
  }

  // 6 ================= EJM
  {
    const s = pres.addSlide({ masterName: "Мятный" });
    chip(s, "Отдел HR · EJM", MX, 0.35);
    s.addText("Мы рядом на всём твоём пути", { placeholder: "title" });
    T(s, "Employee Journey Map — карта пути сотрудника: на каждом этапе у нас есть, чем помочь", { x: MX, y: 1.65, w: 11.5, h: 0.4, fontSize: 16, color: MUTED });
    const st = [[fa.FaHandshake, "Найм", "Знакомимся и зовём в команду"], [fa.FaSeedling, "Адаптация", "Помогаем влиться и освоиться"], [fa.FaHeart, "Вовлечённость", "Чтобы было интересно и тепло"], [fa.FaGraduationCap, "Обучение", "Делимся знаниями и навыками"], [fa.FaChartLine, "Рост и развитие", "Двигаемся вперёд вместе"], [fa.FaBullhorn, "HR-бренд", "Рассказываем, какие мы"]];
    const x0 = 1.5, x1 = W - 1.5, cy = 3.35, A = 0.45;
    const f = (t) => cy + A * Math.sin(t * Math.PI * 2.5 - 0.5);
    for (let k = 0; k <= 70; k++) { const t = k / 70; circle(s, x0 + t * (x1 - x0) - 0.06, f(t) - 0.06, 0.12, MINT3, "Путь " + k); }
    for (let i = 0; i < 6; i++) {
      const t = i / 5, x = x0 + t * (x1 - x0), y = f(t), hi = i === 0 || i === 5;
      circle(s, x - 0.62, y - 0.62, 1.24, hi ? GD : G, "Этап " + (i + 1));
      s.addImage({ data: await ico(st[i][0], WHITE), x: x - 0.27, y: y - 0.27, w: 0.54, h: 0.54, altText: st[i][1] });
      T(s, st[i][1], { x: x - 0.95, y: 4.6, w: 1.9, h: 0.65, fontSize: 17, bold: true, color: OL, align: "center", valign: "top" });
      T(s, st[i][2], { x: x - 0.95, y: 5.3, w: 1.9, h: 0.9, fontSize: 14, color: MUTED, align: "center" });
    }
    s.addNotes("Шесть этапов пути сотрудника; дальше — подробнее про найм, адаптацию и HR-бренд.");
  }

  // 7 ================= НАЙМ
  {
    const s = pres.addSlide({ masterName: "Узкий" });
    rect(s, 6.55, 0, W - 6.55, H, G, "Панель воронки");
    chip(s, "EJM · Найм", MX, 0.35);
    T(s, "95", { x: MX - 0.05, y: 2.0, w: 5.7, h: 2.7, fontSize: 190, bold: true, color: G });
    s.addText("Найм: как мы собираем команду", { placeholder: "title" });
    T(s, "новых коллег вышли на работу из 5 866 откликов", { x: MX, y: 4.75, w: 5.2, h: 0.9, fontSize: 22, bold: true, color: OL });
    T(s, "Примерно каждый 60-й отклик превращается в коллегу — и ты один из них", { x: MX, y: 5.8, w: 5.2, h: 0.8, fontSize: 15, color: MUTED });
    const f = [["Отклики", "5 866", 5.9], ["Первый контакт", "1 038", 5.3], ["Приглашение на собеседование", "743", 4.7], ["Собеседование", "576", 4.1], ["Оффер", "100", 3.5], ["Выход", "95", 2.9]];
    f.forEach((r, i) => {
      const y = 1.2 + i * 0.88, last = i === 5, w = r[2], x = 6.55 + 0.35 + (5.9 - w) / 2;
      rect(s, x, y, w, 0.72, last ? MINT : WHITE, "Шаг " + r[0], 0.36);
      T(s, r[0], { x: x + 0.3, y, w: w - 1.5, h: 0.72, fontSize: 14, color: OL, valign: "middle" });
      T(s, r[1], { x: x + w - 1.4, y, w: 1.1, h: 0.72, fontSize: 20, bold: true, color: last ? GD : G, align: "right", valign: "middle" });
    });
    T(s, "*данные на 31.12.2025", { x: 6.9, y: 6.75, w: 4, h: 0.3, fontSize: 11, color: WHITE });
    s.addNotes("Ширина полос условная. Данные на 31.12.2025.");
  }

  // 8 ================= АДАПТАЦИЯ
  {
    const s = pres.addSlide({ masterName: "Фото слева" });
    s.addImage({ path: I("team_full.jpg"), x: 0, y: 0, w: 6.4, h: 7.5, objectName: "Фото команды", altText: "Команда за рабочим столом" });
    comma(s, "comma_green.png", 5.2, 5.4, 1.2, "Акцент");
    const x0 = 7.0;
    T(s, "EJM · АДАПТАЦИЯ И РАЗВИТИЕ", { x: x0, y: 0.55, w: 6, h: 0.3, fontSize: 12, bold: true, color: GD, charSpacing: 3 });
    s.addText("Чтобы с первого дня было комфортно", { placeholder: "title" });
    const it = [["Welcome-встреча", "Знакомимся и рассказываем, как у нас всё устроено"], ["Неделя адаптации", "Просим короткую анкету: нам важно твоё мнение"], ["Обучение", "«Игра по неподачам», «Системный руководитель», «Академия i’way»"], ["Переходы внутри компании", "Поддерживаем, если решишь сменить роль или команду"]];
    it.forEach((r, i) => {
      const y = 2.65 + i * 1.1;
      T(s, "0" + (i + 1), { x: x0, y, w: 1.0, h: 0.8, fontSize: 40, bold: true, color: G });
      T(s, r[0], { x: x0 + 1.15, y: y + 0.02, w: 4.5, h: 0.35, fontSize: 18, bold: true, color: OL });
      T(s, r[1], { x: x0 + 1.15, y: y + 0.4, w: 4.5, h: 0.6, fontSize: 14, color: MUTED });
    });
    s.addNotes("Рассказать про welcome-встречу и анкеты. Названия программ оставляем как есть.");
  }
  // title width for this slide is set by master; override handled below via narrower text (title wraps to 2 lines)

  // 9 ================= HR-БРЕНД
  {
    const s = pres.addSlide({ masterName: "Раздельный" });
    rect(s, 0, 0, W / 2, H, G, "Снаружи");
    rect(s, W / 2, 0, W / 2, H, MINT, "Внутри");
    s.addText("HR-бренд", { placeholder: "title" });
    const L = ["Карьерные сайты: hh.ru и LinkedIn", "Наружная реклама: метро и экраны", "Работа с университетами", "Ответы на отзывы на площадках"];
    const R = ["Миссия и ценности", "Внутренние коммуникации", "Мотивация и бенефиты", "EVP — уникальное ценностное предложение"];
    T(s, "Снаружи", { x: MX, y: 2.0, w: 5.5, h: 1.1, fontSize: 60, bold: true, color: WHITE });
    T(s, "Внутри", { x: W / 2 + MX, y: 2.0, w: 5.5, h: 1.1, fontSize: 60, bold: true, color: GD });
    T(s, L.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < 3 } })), { x: MX, y: 3.5, w: 5.4, h: 3.0, fontSize: 18, color: WHITE, paraSpaceAfter: 14 });
    T(s, R.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < 3 } })), { x: W / 2 + MX, y: 3.5, w: 5.4, h: 3.0, fontSize: 18, color: OL, paraSpaceAfter: 14 });
    chip(s, "EJM · HR-бренд", W - MX - 2.6, 0.35, WHITE, GD);
    s.addNotes("Снаружи — как нас видят кандидаты, внутри — как мы живём.");
  }

  divider("02", "Культура i’way", "Во что мы верим и как работаем вместе", "Раздел глубокий", MINT, WHITE, "comma_green.png");

  // 11 ================= О КОМПАНИИ
  {
    const s = pres.addSlide({ masterName: "Белый" });
    comma(s, "comma_mint.png", 9.6, 2.6, 5.4, "Апостроф");
    chip(s, "Культура i’way", MX, 0.35);
    s.addText("i’way — трансферы по всему миру", { placeholder: "title" });
    T(s, "130+", { x: MX - 0.05, y: 1.7, w: 7, h: 2.6, fontSize: 190, bold: true, color: G });
    T(s, "стран, где мы возим людей", { x: MX, y: 4.5, w: 6, h: 0.5, fontSize: 24, bold: true, color: OL });
    [["2 500+", "поездок ежедневно", GD, WHITE], ["600+", "аэропортов мира", MINT, OL]].forEach((r, i) => {
      const y = 1.9 + i * 2.15;
      rect(s, 7.9, y, 4.7, 1.9, r[2], "Цифра " + r[1], 0.3);
      T(s, r[0], { x: 8.25, y: y + 0.2, w: 4.0, h: 1.1, fontSize: 56, bold: true, color: r[3] });
      T(s, r[1], { x: 8.25, y: y + 1.3, w: 4.0, h: 0.4, fontSize: 18, color: r[3] });
    });
    [["с 2009", "на рынке"], ["4,9 из 5", "оценка поездок"], ["Офисы", "в Казахстане, ОАЭ, Индии"]].forEach((r, i) => {
      const x = MX + i * 2.4;
      T(s, r[0], { x, y: 5.4, w: 2.3, h: 0.5, fontSize: 24, bold: true, color: GD });
      T(s, r[1], { x, y: 5.95, w: 2.2, h: 0.6, fontSize: 14, color: MUTED });
    });
    s.addNotes("130+ стран, 2 500+ поездок и 600+ аэропортов — из внутренней презентации. Оценка 4,9, офисы в Казахстане, ОАЭ и Индии — по данным Felo-поиска (App Store, блог i’way, Forbes.kz).");
  }

  // 12 ================= ДАШБОРД
  {
    const s = pres.addSlide({ masterName: "Зелёный" });
    s.addImage({ path: I("dash.png"), x: W - MX - 7.4, y: 1.6, w: 7.4, h: 4.18, objectName: "Дашборд", altText: "Панель с онлайн-метриками" });
    s.addText("Наш день в цифрах", { placeholder: "title" });
    T(s, "Бронирования, выручка и оценки клиентов — всё на одном экране, в реальном времени.", { x: MX, y: 3.0, w: 4.4, h: 1.6, fontSize: 22, bold: true, color: WHITE });
    T(s, "Каждый из нас влияет на эти цифры.", { x: MX, y: 5.0, w: 4.4, h: 0.8, fontSize: 18, color: WHITE });
    s.addNotes("Скриншот внутреннего дашборда. Перед показом широкой аудитории проверьте конфиденциальность цифр.");
  }

  // 13 ================= ИСТОРИЯ
  {
    const s = pres.addSlide({ masterName: "Мятный" });
    s.addImage({ path: I("c_founders.png"), x: W - 4.3 - 0.4, y: 1.0, w: 4.3, h: 5.44, objectName: "Основатели", altText: "Основатели i’way" });
    chip(s, "Культура i’way · История", MX, 0.35);
    s.addText("Как всё начиналось", { placeholder: "title" });
    const ev = [["2009", "ООО «Сибирская трансферная компания»"], ["2011", "iWay Express: двуязычный сайт с онлайн-бронированием"], ["2013", "Родился бренд i’way"], ["2023", "Открыли офис в Казахстане"]];
    ev.forEach((r, i) => {
      const x = MX + (i % 2) * 4.3, y = 2.2 + Math.floor(i / 2) * 2.35;
      T(s, r[0], { x, y, w: 4, h: 1.1, fontSize: 72, bold: true, color: i === 3 ? GD : G });
      T(s, r[1], { x, y: y + 1.15, w: 3.3, h: 0.9, fontSize: 17, color: OL });
    });
    s.addNotes("Даты 2009–2013 — из внутренней презентации; офис в Казахстане (начало 2023, Алматы) — Forbes.kz, по данным Felo-поиска.");
  }

  // 14 ================= МИССИЯ
  {
    const s = pres.addSlide({ masterName: "Глубокий" });
    comma(s, "comma_green.png", 9.0, 1.8, 6.0, "Апостроф");
    s.addText("Миссия", { placeholder: "title" });
    T(s, "i’way меняет представление о транспортном сервисе в России и мире и, ориентируясь на потребности клиентов, выступает законодателем стандартов обслуживания.", { x: MX, y: 1.9, w: 9.6, h: 4.4, fontSize: 38, bold: true, color: WHITE });
    logoW(s, MX, 6.5, 1.0);
    s.addNotes("Миссия — формулировка без изменений.");
  }

  // 15 ================= ЦЕННОСТИ
  {
    const s = pres.addSlide({ masterName: "Мятный" });
    chip(s, "Культура i’way · Бренд-код", MX, 0.35);
    s.addText("Наши ценности", { placeholder: "title" });
    logoD(s, W - MX - 1.5, 0.55, 1.5);
    const v = [
      ["Открытость", "Готовность принимать новое, прислушиваться к просьбам и проблемам клиентов; старание быть нужным.", GD, WHITE, WHITE, 0, 0, 4.0, 4.7],
      ["Честность", "Соблюдение делового этикета и корпоративной политики; неприятие обмана и хитростей в корыстных целях.", MINT, OL, GD, 1, 0, 3.9, 2.3],
      ["Лидерство", "Предоставление клиентам лучшего; ввод новых стандартов обслуживания.", WHITE, OL, GD, 1, 1, 3.9, 2.3],
      ["Технологичность", "Внедрение современных решений.", MINT3, OL, GD, 2, 0, 3.7, 2.3],
      ["Человечность", "Уважительное отношение; дружелюбие в общении.", GD, WHITE, MINT, 2, 1, 3.7, 2.3],
    ];
    const colx = [MX, MX + 4.2, MX + 8.3];
    v.forEach((r) => {
      const x = colx[r[5]], y = 1.9 + r[6] * 2.4;
      rect(s, x, y, r[7], r[8], r[2], "Ценность " + r[0], 0.3);
      comma(s, r[2] === GD ? "comma_green.png" : "comma_g.png", x + 0.3, y + 0.3, 0.3, "Апостроф");
      T(s, r[0], { x: x + 0.3, y: y + (r[8] > 3 ? 0.9 : 0.75), w: r[7] - 0.6, h: 0.5, fontSize: r[8] > 3 ? 32 : 22, bold: true, color: r[4] });
      T(s, r[1], { x: x + 0.3, y: y + (r[8] > 3 ? 1.65 : 1.25), w: r[7] - 0.6, h: r[8] - (r[8] > 3 ? 1.8 : 1.35), fontSize: r[8] > 3 ? 18 : 14, color: r[3] });
    });
    s.addNotes("Ценности — формулировки из бренд-кода, без изменений.");
  }

  // 16 ================= КАК У НАС ПРИНЯТО
  {
    const s = pres.addSlide({ masterName: "Левая колонка" });
    comma(s, "comma_white.png", MX, 1.0, 1.2, "Апостроф");
    s.addText("Как у нас принято", { placeholder: "title" });
    T(s, "Пять правил, по которым мы живём и работаем", { x: MX, y: 5.2, w: 4.0, h: 1.0, fontSize: 18, color: WHITE });
    const r = [[fa.FaTshirt, "Дресс-код", "Smart Casual: выглядим опрятно и остаёмся собой"], [fa.FaUserFriends, "Руководитель рядом", "Он — первая точка входа для любого вопроса"], [fa.FaShieldAlt, "Ответственность", "Отвечаем за результат и держим слово"], [fa.FaLightbulb, "Идеи приветствуются", "Предложил полезное — поможем воплотить"], [fa.FaHeart, "Неравнодушие", "Нам не всё равно — к клиентам и друг к другу"]];
    for (let i = 0; i < 5; i++) {
      const y = 0.55 + i * 1.3;
      rect(s, 5.5, y, 7.1, 1.15, i % 2 ? MINT : WHITE, "Правило " + (i + 1), 0.57);
      circle(s, 5.6, y + 0.1, 0.95, i % 2 ? WHITE : G, "Круг " + (i + 1));
      s.addImage({ data: await ico(r[i][0], i % 2 ? G : WHITE), x: 5.6 + 0.3, y: y + 0.4, w: 0.35, h: 0.35, altText: r[i][1] });
      T(s, r[i][1], { x: 6.8, y: y + 0.17, w: 5.6, h: 0.4, fontSize: 19, bold: true, color: OL });
      T(s, r[i][2], { x: 6.8, y: y + 0.6, w: 5.6, h: 0.4, fontSize: 14, color: OL });
    }
    s.addNotes("Пять принципов корпоративной культуры из внутренней презентации, переформулированы дружелюбнее.");
  }

  // 17 ================= АПОСТРОФ
  {
    const s = pres.addSlide({ masterName: "Мятный" });
    chip(s, "Культура i’way · Маленькая деталь", MX, 0.35);
    s.addText("Наш апостроф — особенный", { placeholder: "title" });
    rect(s, MX, 1.95, 5.3, 4.5, WHITE, "Плитка логотипа", 0.35);
    logoD(s, MX + 0.7, 2.75, 3.9);
    const rows = [["i’way", true, "Правильно — с красивым апострофом", 66], ["i'way", false, "Не так — прямой апостроф", 40], ["i`way", false, "И не так — обратный апостроф", 40]];
    let y = 1.9;
    for (const r of rows) {
      T(s, r[0], { x: 6.5, y, w: 4.2, h: r[3] > 50 ? 1.2 : 0.75, fontSize: r[3], bold: true, color: r[1] ? G : "9AA396", valign: "middle" });
      T(s, r[2], { x: 6.5, y: y + (r[3] > 50 ? 1.2 : 0.75), w: 5.2, h: 0.35, fontSize: 15, color: MUTED });
      circle(s, 11.8, y + (r[3] > 50 ? 0.3 : 0.1), 0.6, r[1] ? G : MUTED, r[1] ? "Верно" : "Неверно");
      s.addImage({ data: await ico(r[1] ? fa.FaCheck : fa.FaTimes, WHITE), x: 11.97, y: y + (r[3] > 50 ? 0.47 : 0.27), w: 0.26, h: 0.26, altText: r[1] ? "верно" : "неверно" });
      y += r[3] > 50 ? 1.65 : 1.1;
    }
    // keycaps
    T(s, "Windows:", { x: 6.5, y: 6.0, w: 1.5, h: 0.6, fontSize: 16, color: OL, valign: "middle" });
    [["Alt", 8.0, 0.95], ["+", 9.05, 0.4], ["0146", 9.55, 1.4]].forEach(([t, x, w]) => {
      if (t === "+") { T(s, t, { x, y: 6.0, w, h: 0.6, fontSize: 22, bold: true, color: GD, align: "center", valign: "middle" }); return; }
      rect(s, x, 6.0, w, 0.6, WHITE, "Клавиша " + t, 0.12);
      T(s, t, { x, y: 6.0, w, h: 0.6, fontSize: 20, bold: true, color: GD, align: "center", valign: "middle" });
    });
    s.addNotes("Пишем i’way с типографским апострофом (Alt+0146).");
  }

  divider("03", "Команда i’way", "Люди, благодаря которым всё работает", "Раздел мятный", G, GD, "comma_g.png");

  // 19 ================= ДИРЕКЦИЯ
  {
    const s = pres.addSlide({ masterName: "Белый" });
    chip(s, "Команда i’way", MX, 0.35);
    s.addText("Дирекция i’way", { placeholder: "title" });
    const d = [["D1.jpg", "Дмитрий Салихов", "CEO, основатель i’way", GD], ["D2.jpg", "Дмитрий Сарайкин", "Сооснователь i’way", G], ["D3.jpg", "Александр Шведов", "CTO, исполнительный директор", GD], ["D5.jpg", "Джехад Абугсиса", "Директор по международному развитию", G]];
    d.forEach((p, i) => {
      const x = i * (W / 4), cw = W / 4;
      s.addImage({ path: I(p[0]), x, y: 1.95, w: cw, h: 3.75, objectName: p[1], altText: p[1] });
      rect(s, x, 5.7, cw, 1.8, p[3], "Подпись " + p[1]);
      T(s, p[1], { x: x + 0.3, y: 5.9, w: cw - 0.5, h: 0.4, fontSize: 20, bold: true, color: WHITE });
      T(s, p[2], { x: x + 0.3, y: 6.35, w: cw - 0.5, h: 0.9, fontSize: 14, color: WHITE });
    });
    s.addNotes("Слайд Ольги Чикан (операционный директор) был скрыт в исходной презентации, поэтому здесь её нет.");
  }

  // 20 ================= ЦИФРЫ КОМАНДЫ
  {
    const s = pres.addSlide({ masterName: "Зелёный" });
    comma(s, "comma_green.png", 8.3, -1.5, 6.5, "Апостроф");
    s.addText("Мы — команда", { placeholder: "title" });
    T(s, "160+", { x: MX - 0.05, y: 1.5, w: 7.3, h: 3.2, fontSize: 190, bold: true, color: WHITE });
    T(s, "коллег в команде i’way", { x: MX, y: 4.85, w: 6, h: 0.6, fontSize: 26, bold: true, color: MINT });
    const st = [[fa.FaFemale, "100+", "девушек"], [fa.FaMale, "50+", "парней"], [fa.FaBirthdayCake, "32", "года — средний возраст"]];
    for (let i = 0; i < 3; i++) {
      const y = 1.95 + i * 1.5;
      rect(s, 8.0, y, 4.6, 1.3, WHITE, "Плитка " + st[i][2], 0.65);
      circle(s, 8.15, y + 0.15, 1.0, MINT, "Круг " + (i + 1));
      s.addImage({ data: await ico(st[i][0], GD), x: 8.45, y: y + 0.45, w: 0.4, h: 0.4, altText: st[i][2] });
      T(s, st[i][1], { x: 9.35, y: y + 0.12, w: 1.9, h: 0.75, fontSize: 40, bold: true, color: G, valign: "middle" });
      T(s, st[i][2], { x: 9.35, y: y + 0.82, w: 3.1, h: 0.35, fontSize: 14, color: OL });
    }
    s.addNotes("Данные из внутренней презентации.");
  }

  // 21 ================= КАРТА
  {
    const s = pres.addSlide({ masterName: "Глубокий" });
    s.addText("Где нас можно встретить", { placeholder: "title" });
    T(s, "Города России и страны, где работает i’way", { x: MX, y: 2.35, w: 2.8, h: 1.8, fontSize: 20, bold: true, color: MINT });
    T(s, "Мы всё ближе к клиентам и партнёрам по всему миру", { x: MX, y: 4.4, w: 2.8, h: 1.4, fontSize: 15, color: WHITE });
    s.addImage({ path: I("map.png"), x: W - MX - 8.9, y: 1.75, w: 8.9, h: 4.9, objectName: "Карта", altText: "Карта присутствия i’way" });
    s.addNotes("Города России и страны присутствия — по карте.");
  }

  // 22–24 ================= КВИЗ
  const quiz = (n, q, a, b, right, note, m) => {
    const s = pres.addSlide({ masterName: m });
    chip(s, `Мини-квиз · вопрос ${n} из 3`, MX, 0.35, WHITE, GD);
    s.addText(q, { placeholder: "title" });
    [a, b].forEach((t, i) => {
      const x = MX + i * 6.1;
      rect(s, x, 3.7, 5.8, 2.7, WHITE, "Вариант " + "AB"[i], 0.35);
      circle(s, x + 0.35, 4.05, 0.85, i ? GD : G, "Буква " + "AB"[i]);
      T(s, "AB"[i], { x: x + 0.35, y: 4.05, w: 0.85, h: 0.85, fontSize: 30, bold: true, color: WHITE, align: "center", valign: "middle" });
      T(s, t, { x: x + 1.5, y: 3.95, w: 4.0, h: 2.2, fontSize: 21, bold: true, color: OL, valign: "middle" });
    });
    s.addNotes("Правильный ответ: " + "AB"[right] + ". " + note);
  };
  quiz(1, "Какая главная задача отдела HR в i’way?", "Укомплектованность штата", "Создать сильную команду для роста компании", 1, "Создать сильную команду для роста компании.", "Вопрос");
  quiz(2, "Ценность «открытость» — это…", "Готовность принимать новое и прислушиваться к потребностям клиентов", "Принцип «открытых дверей»: с идеей можно прийти к руководителю", 0, "Готовность принимать новое и прислушиваться к потребностям клиентов.", "Вопрос глубокий");
  quiz(3, "Кто в i’way главный?", "Клиент", "CEO", 0, "Клиент.", "Вопрос");

  // 25 ================= ОТВЕТЫ
  {
    const s = pres.addSlide({ masterName: "Мятный" });
    chip(s, "Мини-квиз · ответы", MX, 0.35);
    s.addText("Проверяем себя", { placeholder: "title" });
    const a = [["1", "Главная задача HR", "Создать сильную команду для роста компании"], ["2", "Открытость — это", "Готовность принимать новое и слышать клиентов"], ["3", "Главный в i’way", "Клиент"]];
    a.forEach((r, i) => {
      const y = 2.0 + i * 1.5;
      rect(s, MX, y, 11.9, 1.25, i === 1 ? MINT : WHITE, "Ответ " + r[0], 0.62);
      T(s, r[0], { x: MX + 0.4, y, w: 1, h: 1.25, fontSize: 54, bold: true, color: G, valign: "middle" });
      T(s, r[1], { x: MX + 1.6, y, w: 3.2, h: 1.25, fontSize: 16, color: MUTED, valign: "middle" });
      T(s, r[2], { x: MX + 4.9, y, w: 6.7, h: 1.25, fontSize: 22, bold: true, color: OL, valign: "middle" });
    });
    s.addNotes("Если ошиблись — не страшно: всё это ещё не раз пригодится.");
  }

  // 26 ================= СПАСИБО
  {
    const s = pres.addSlide({ masterName: "Финал" });
    logoW(s, MX, 0.65, 1.6);
    s.addText("Спасибо!", { placeholder: "title" });
    T(s, "Мы всегда на связи: пиши, звони или заходи — поможем и подскажем.", { x: MX, y: 4.3, w: 6.2, h: 1.0, fontSize: 22, color: WHITE });
    rect(s, MX, 5.6, 3.6, 0.8, MINT, "Почта", 0.4);
    T(s, "hr@iway.ru", { x: MX, y: 5.6, w: 3.6, h: 0.8, fontSize: 26, bold: true, color: GD, align: "center", valign: "middle" });
    [["c_julia.png", 7.4, 1.4], ["c_anna.png", 9.4, 3.2], ["c_elena.png", 11.4, 1.4]].forEach(([f, x, y], i) => {
      s.addImage({ path: I(f), x, y, w: 1.9, h: 1.9 * 4.17 / 3.3, objectName: "Портрет " + (i + 1), altText: "Сотрудник HR" });
    });
    s.addNotes("Адрес hr@iway.ru — взят из репозитория HR-портала; проверьте перед показом.");
  }

  // 27–28 ================= QR
  const qr = (title, sub, qrf, notes, m) => {
    const s = pres.addSlide({ masterName: m });
    s.addText(title, { placeholder: "title" });
    T(s, sub, { x: MX, y: 4.5, w: 5.4, h: 1.2, fontSize: 22, color: WHITE });
    rect(s, 8.0, 1.4, 4.6, 4.6, WHITE, "Подложка QR", 0.35);
    s.addImage({ path: qrf, x: 8.3, y: 1.7, w: 4.0, h: 4.0, objectName: "QR-код", altText: "QR-код" });
    s.addNotes(notes);
  };
  qr("Поделись обратной связью", "Нам важно твоё мнение — наведи камеру на QR-код", "../src/x/ppt/media/image24.png", "QR-код из исходной презентации.", "QR");
  qr("Оставь оценку", "Это займёт меньше минуты — спасибо!", "../src/x/ppt/media/image25.png", "QR-код из исходной презентации (слайд назывался «Оценка»). Проверьте, куда он ведёт.", "QR глубокий");

  await pres.writeFile({ fileName: "deck.pptx" });
  await applyTheme("deck.pptx", THEME);
  console.log("done");
})();
