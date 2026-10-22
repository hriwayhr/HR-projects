'use strict';
// Права доступа к документам. Сервер — единственное место, где они проверяются:
// страница может показывать что угодно, но получит и запишет только разрешённое здесь.
//
// user = {pid, email, admin, role} — человек из config/team (role: admin | hr) или новичок из employees (role: employee, code).
// Портал: HR Preboard (employees, config/departments|page|templates) — правят администратор и HR, новичок видит и отмечает только своё;
// HR-метрики (остальное) — права команды как были: администратор всё, рекрутер своё.

const PATH_RE = /^(config|months|vacations|vacancies|rejections|employees)\/[A-Za-z0-9_-]{1,100}$/;
const PRE_CONFIG = ['departments', 'page', 'templates'];
const isPreboard = path => { const [c, id] = path.split('/'); return c === 'employees' || (c === 'config' && PRE_CONFIG.includes(id)); };
// что новичок отмечает на своей странице сам; остальное в его карточке (пароль, логин, оффер) — только HR
const EMP_FIELDS = ['openedAt', 'firstTime', 'progress', 'cardChoice', 'docsSentAt', 'updatedAt'];
// что можно записать в эти поля: страница пишет только такое — остальное отсекаем, чтобы в карточку не попала разметка или мусор
const isIso = v => typeof v === 'string' && v.length <= 40 && !isNaN(Date.parse(v));
const boolMap = v => v !== null && typeof v === 'object' && !Array.isArray(v) && Object.keys(v).length <= 100 &&
  Object.keys(v).every(k => /^[A-Za-z0-9_-]{1,60}$/.test(k) && typeof v[k] === 'boolean');
const EMP_CHECK = { openedAt: isIso, docsSentAt: isIso, updatedAt: isIso, cardChoice: v => ['', 'need', 'have'].includes(v), progress: boolMap, firstTime: boolMap };
const sameJson = (a, b) => JSON.stringify(a === undefined ? null : a) === JSON.stringify(b === undefined ? null : b);
const MAX_DOC = 256 * 1024;

function norm(s) { return String(s || '').trim().toLowerCase(); }

// Чья вакансия: в «Ответственном» фамилия пользователя, а если фамилии нет — имя (как на странице)
function ownerOf(manager, people) {
  const m = norm(manager);
  if (!m) return null;
  const ids = Object.keys(people || {}).sort((a, b) => (people[a].order || 0) - (people[b].order || 0) || String(people[a].name).localeCompare(String(people[b].name)));
  const has = f => ids.find(p => { const x = norm(people[p][f]); return x && m.includes(x); });
  return has('surname') || has('name') || null;
}

// Кто из команды: по корпоративной почте; в архиве — не пускаем
// field — по чему узнаём человека: почта (вход через Яндекс) или логин (локальная версия с паролями)
function userByEmail(people, email, field = 'email') {
  const e = norm(email);
  const pid = Object.keys(people || {}).find(p => norm(people[p][field]) === e);
  if (!pid || people[pid].archived) return null;
  return { pid, email: e, admin: !!people[pid].admin, role: people[pid].admin ? 'admin' : 'hr', field };
}

// Отпуск с передачей вакансий: в дни отпуска владельца его вакансии ведёт sub из записи отпуска (vacations/<pid>.list[].sub).
// Дата — московская: смена дня в полночь по Москве, а не по UTC.
function todayMsk() { return new Date(Date.now() + 3 * 3600e3).toISOString().slice(0, 10); }
function coverOf(owner, vacations, day) {
  const x = ((vacations || {})[owner] || []).find(v => v && v.from <= day && day <= v.to);
  return x && x.sub && x.sub !== owner ? x.sub : null;
}
// чьи вакансии пользователь ведёт сейчас: свои и тех, кого он подменяет в отпуске
function ownersFor(user) {
  const day = todayMsk(), out = [user.pid];
  Object.keys(user.vacations || {}).forEach(p => { if (coverOf(p, user.vacations, day) === user.pid) out.push(p); });
  return out;
}

const PUBLIC_PERSON = ['name', 'surname', 'order', 'admin', 'recruiter', 'archived', 'archivedAt', 'since', 'syncFrom'];

// Что пользователь увидит из документа; null — ничего
function readable(user, path, data, people) {
  const [coll, id] = path.split('/');
  if (user.role === 'employee') {
    if (coll === 'employees' && id === user.code) { const out = Object.assign({}, data); delete out.hash; delete out.salt; return out; }
    return coll === 'config' && (id === 'departments' || id === 'page') ? data : null;
  }
  if (isPreboard(path)) return data;
  if (coll === 'config' && id === 'team') {
    if (user.admin) return data;
    const out = {};
    Object.keys(data.people || {}).forEach(p => { out[p] = {}; PUBLIC_PERSON.forEach(k => { if (k in data.people[p]) out[p][k] = data.people[p][k]; }); });
    return { people: out };
  }
  if (coll === 'config' && id === 'metrics') return data;
  if (user.admin) return data;
  if (coll === 'months') return data.person === user.pid ? data : null;
  // отпуск коллеги, на время которого вакансии переданы пользователю, — чтобы страница знала, что и до какого дня он ведёт
  if (coll === 'vacations') return id === user.pid || (data.list || []).some(v => v && v.sub === user.pid) ? data : null;
  if (coll === 'vacancies') return ownersFor(user).includes(ownerOf(data.manager, people)) ? data : null;
  if (coll === 'rejections') {
    const items = (data.items || []).filter(x => ownerOf(x.w, people) === user.pid);
    return items.length ? Object.assign({}, data, { items }) : null;
  }
  return null;
}

// Можно ли записать next (null — удалить) поверх prev (null — документа нет). Возвращает текст ошибки или ''.
function writeError(user, path, prev, next, people) {
  if (!PATH_RE.test(path)) return 'Недопустимый путь.';
  if (next !== null) {
    if (typeof next !== 'object' || Array.isArray(next)) return 'Документ должен быть объектом.';
    if (Buffer.byteLength(JSON.stringify(next)) > MAX_DOC) return 'Документ больше 256 КБ.';
  }
  const [coll, id] = path.split('/');
  if (user.role === 'employee') {
    if (coll !== 'employees' || id !== user.code || !prev || !next) return 'Нет прав.';
    const keys = new Set(Object.keys(prev).concat(Object.keys(next)));
    for (const k of keys) {
      if (!EMP_FIELDS.includes(k)) { if (!sameJson(prev[k], next[k])) return 'Можно отмечать только свои шаги.'; }
      else if (next[k] !== undefined && !sameJson(prev[k], next[k]) && !EMP_CHECK[k](next[k])) return 'Неверное значение отметки.';
    }
    return '';
  }
  if (coll === 'employees') {
    if (!next) return '';
    if (next.code !== id) return 'Код не совпадает с адресом.';
    // без https браузер не умеет SHA-256 и страница записала бы пароль открытым текстом
    if (next.hash !== undefined && !/^[0-9a-f]{64}$/.test(String(next.hash))) return 'Пароль не зашифрован — откройте портал по https.';
    // логин новичка не должен совпадать со входом команды: вход сначала ищет команду, и новичок бы не вошёл
    const taken = [norm(next.login), norm(next.email)].filter(Boolean).find(v => Object.keys(people || {}).some(p => norm(people[p].login) === v || norm(people[p].email) === v));
    return taken ? 'Логин «' + taken + '» уже занят в команде.' : '';
  }
  if (coll === 'config' && PRE_CONFIG.includes(id)) return '';
  if (coll === 'config') {
    if (!user.admin) return 'Настройки меняет администратор.';
    if (id === 'team') return teamError(user, next);
    if (id === 'metrics') return next && Array.isArray(next.list) ? '' : 'Нужен список метрик.';
    return 'Недопустимый путь.';
  }
  if (user.admin) {
    if (coll === 'months' && next && !(next.person && id === next.person + '_' + next.month)) return 'Месяц не совпадает с адресом.';
    return '';
  }
  if (coll === 'months') {
    if (!id.startsWith(user.pid + '_')) return 'Можно вносить только свои цифры.';
    if (next && (next.person !== user.pid || id !== user.pid + '_' + next.month)) return 'Можно вносить только свои цифры.';
    return '';
  }
  if (coll === 'vacations') return id === user.pid ? '' : 'Можно менять только свой отпуск.';
  if (coll === 'vacancies') {
    if (next === null) return 'Удаляет вакансию администратор.';
    const mineNow = ownersFor(user);
    if (prev && !mineNow.includes(ownerOf(prev.manager, people))) return 'Это вакансия другого рекрутера.';
    if (!mineNow.includes(ownerOf(next.manager, people))) return 'Ответственным должны быть вы.';
    return '';
  }
  return 'Нет прав.';
}

// Команда: у каждого — имя; почты уникальны; остаётся хотя бы один действующий администратор с почтой,
// и администратор не может снять права или вход с самого себя — так в команде всегда есть кто-то с доступом.
function teamError(user, next) {
  if (!next || typeof next.people !== 'object' || Array.isArray(next.people)) return 'Нужен список людей.';
  const ps = next.people, seen = {};
  for (const p of Object.keys(ps)) {
    if (!/^[A-Za-z0-9_-]{1,40}$/.test(p) || !ps[p] || !String(ps[p].name || '').trim()) return 'У каждого в команде должно быть имя.';
    const e = norm(ps[p].email);
    if (e) {
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)) return 'Почта «' + e + '» выглядит неверно.';
      if (seen[e]) return 'Почта «' + e + '» уже у другого человека.';
      seen[e] = 1;
    }
    const l = norm(ps[p].login);
    if (l) { if (seen['login:' + l]) return 'Логин «' + l + '» уже у другого человека.'; seen['login:' + l] = 1; }
  }
  // по почте, а не по id: при переносе данных администратор становится человеком из загруженной команды
  // вход по паролю: человек может сменить свой логин (например, на почту) — тогда узнаём его по id
  const me = Object.keys(ps).find(p => norm(ps[p][user.field || 'email']) === user.email) || (user.field === 'login' && ps[user.pid] ? user.pid : undefined);
  if (!me || ps[me].archived || !ps[me].admin) return 'Нельзя снять права администратора или вход с самого себя.';
  return '';
}

module.exports = { ownerOf, userByEmail, readable, writeError, norm, PATH_RE, ownersFor, coverOf, todayMsk, isPreboard };
