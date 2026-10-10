'use strict';
// Права доступа к документам. Сервер — единственное место, где они проверяются:
// страница может показывать что угодно, но получит и запишет только разрешённое здесь.
//
// user = {pid, email, admin} — пользователь из config/team, вошедший через Яндекс ID.

const PATH_RE = /^(config|months|vacations|vacancies|rejections)\/[A-Za-z0-9_-]{1,100}$/;
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
function userByEmail(people, email) {
  const e = norm(email);
  const pid = Object.keys(people || {}).find(p => norm(people[p].email) === e);
  if (!pid || people[pid].archived) return null;
  return { pid, email: e, admin: !!people[pid].admin };
}

const PUBLIC_PERSON = ['name', 'surname', 'order', 'admin', 'recruiter', 'archived', 'archivedAt', 'since'];

// Что пользователь увидит из документа; null — ничего
function readable(user, path, data, people) {
  const [coll, id] = path.split('/');
  if (coll === 'config' && id === 'team') {
    if (user.admin) return data;
    const out = {};
    Object.keys(data.people || {}).forEach(p => { out[p] = {}; PUBLIC_PERSON.forEach(k => { if (k in data.people[p]) out[p][k] = data.people[p][k]; }); });
    return { people: out };
  }
  if (coll === 'config' && id === 'metrics') return data;
  if (user.admin) return data;
  if (coll === 'months') return data.person === user.pid ? data : null;
  if (coll === 'vacations') return id === user.pid ? data : null;
  if (coll === 'vacancies') return ownerOf(data.manager, people) === user.pid ? data : null;
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
    if (prev && ownerOf(prev.manager, people) !== user.pid) return 'Это вакансия другого рекрутера.';
    if (ownerOf(next.manager, people) !== user.pid) return 'Ответственным должны быть вы.';
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
  }
  // по почте, а не по id: при переносе данных администратор становится человеком из загруженной команды
  const me = Object.keys(ps).find(p => norm(ps[p].email) === user.email);
  if (!me || ps[me].archived || !ps[me].admin) return 'Нельзя снять права администратора или вход с самого себя.';
  return '';
}

module.exports = { ownerOf, userByEmail, readable, writeError, norm, PATH_RE };
