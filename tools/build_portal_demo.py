# Демо портала для артефакта: та же страница src/iway-portal.html, а сервер подменён копией в браузере —
# правила доступа берутся из cloud/function/acl.js как есть, данные демонстрационные (в sessionStorage вкладки).
#   python3 tools/build_portal_demo.py OUT.html [папка с config/*.json — отделы, страница, шаблоны]
import hashlib, json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parent.parent
out = pathlib.Path(sys.argv[1])
cfg_dir = pathlib.Path(sys.argv[2]) if len(sys.argv) > 2 else None
sha = lambda s, p: hashlib.sha256((s + '::' + p).encode()).hexdigest()

page = (ROOT / 'src' / 'iway-portal.html').read_text(encoding='utf-8')
acl = (ROOT / 'cloud' / 'function' / 'acl.js').read_text(encoding='utf-8')
index = (ROOT / 'cloud' / 'function' / 'index.js').read_text(encoding='utf-8')
merge = index[index.index('const isObj = '):index.index('async function write(')]

docs = {
  'config/team': {'people': {
    'yulia': {'name': 'Юлия', 'surname': 'Немчинова', 'login': 'yulia', 'email': 'ny@iway.ru', 'salt': 'd1', 'hash': sha('d1', 'demo'), 'admin': True, 'order': 1},
    'anna': {'name': 'Анна', 'surname': 'Шулятицкая', 'login': 'anna', 'email': 'shua@iway.ru', 'salt': 'd2', 'hash': sha('d2', 'demo'), 'recruiter': True, 'order': 2}}},
  'config/departments': {'list': [{'name': 'Клиентский сервис', 'head': 'Руководитель отдела', 'senior': 'Старший смены', 'chat': '@iway_cs'},
                                  {'name': 'Логистика', 'head': 'Руководитель логистики', 'senior': 'Старший логист', 'chat': '@iway_log'}]},
  'employees/IW-DEMO': {'code': 'IW-DEMO', 'login': 'demo', 'email': '', 'firstName': 'Мария', 'lastName': 'Примерова', 'gender': 'f',
                        'dept': 'Клиентский сервис', 'startDate': '2026-11-02', 'startTime': '10:00', 'personalEmail': 'maria@example.com',
                        'salt': 'd3', 'hash': sha('d3', 'demo'), 'sentAt': '2026-10-20T10:00:00Z', 'createdAt': '2026-10-19T10:00:00Z'},
  'employees/IW-DEM2': {'code': 'IW-DEM2', 'login': 'iw-dem2', 'email': '', 'firstName': 'Игорь', 'lastName': 'Образцов', 'gender': 'm',
                        'dept': 'Логистика', 'startDate': '2026-11-16', 'personalEmail': 'igor@example.com', 'createdAt': '2026-10-21T10:00:00Z'},
}
if cfg_dir:   # настоящие отделы, страница сотрудника и шаблоны — чтобы демо выглядело как в работе
    for name in ['departments', 'page', 'templates']:
        f = cfg_dir / (name + '.json')
        if f.exists(): docs['config/' + name] = {k: v for k, v in json.loads(f.read_text(encoding='utf-8')).items() if not k.startswith('__')}

mock = r"""<script>
window.HR_SERVER = true;
(function(){
  /* Демо: сервер портала прямо в браузере. Права — тот же acl.js, что на iteamboard.ru. */
  var module = {exports:{}}, Buffer = {byteLength:function(s){ return new Blob([s]).size; }};
  (function(module, exports){ ACL })(module, module.exports);
  var acl = module.exports;
  MERGE
  var KEY = 'iwayPortalDemo', SEED = DOCS, st = null;
  try{ st = JSON.parse(sessionStorage.getItem(KEY)); }catch(e){}
  if(!st){ st = {ver:1, session:null, docs:{}}; Object.keys(SEED).forEach(function(p){ st.docs[p] = {ver:1, data:SEED[p]}; }); }
  function save(){ try{ sessionStorage.setItem(KEY, JSON.stringify(st)); }catch(e){} }
  function get(p){ return st.docs[p] ? st.docs[p].data : null; }
  function put(p, data){ st.ver++; st.docs[p] = {ver:st.ver, data:data}; save(); return st.ver; }
  function people(){ return (get('config/team') || {}).people || {}; }
  function emps(){ return Object.keys(st.docs).filter(function(p){ return p.indexOf('employees/') === 0 && get(p); }).map(get); }
  function norm(s){ return String(s || '').trim().toLowerCase(); }
  function user(){
    var s = st.session, ps = people();
    if(!s) return null;
    if(s.indexOf('emp:') === 0){
      var rec = get('employees/' + s.slice(4));
      return rec ? {pid:s, email:s, admin:false, role:'employee', code:rec.code, name:[rec.firstName, rec.lastName].join(' '), people:ps, vacations:{}} : null;
    }
    var u = acl.userByEmail(ps, s, 'login');
    if(!u) return null;
    u.people = ps; u.vacations = {}; u.name = [ps[u.pid].name, ps[u.pid].surname].filter(Boolean).join(' ');
    return u;
  }
  function hash(salt, pw){
    return crypto.subtle.digest('SHA-256', new TextEncoder().encode(salt + '::' + pw)).then(function(b){
      return Array.prototype.map.call(new Uint8Array(b), function(x){ return ('0' + x.toString(16)).slice(-2); }).join('');
    });
  }
  function handle(url, method, b){
    var path = url.split('?')[0], ps = people(), u;
    if(path === '/api/plogin'){
      var l = norm(b.login), pid = Object.keys(ps).filter(function(p){ return norm(ps[p].login) === l || (ps[p].login && norm(ps[p].email) === l); })[0];
      var t = pid && ps[pid], sess = t && norm(t.login);
      if(!t){
        var list = emps();
        t = list.filter(function(e){ return norm(e.login) === l; })[0] || list.filter(function(e){ return norm(e.email) === l; })[0] || list.filter(function(e){ return norm(e.code) === l; })[0];
        sess = t && 'emp:' + t.code;
      }
      return hash((t && t.salt) || '', b.password || '').then(function(h){
        if(!t || !t.hash || h !== t.hash) return [401, {error:'Неверный логин или пароль.'}];
        st.session = sess; save(); return [200, {ok:true}];
      });
    }
    if(path === '/api/logout'){ st.session = null; save(); return [200, {ok:true}]; }
    if(!(u = user())) return [401, {error:'Нужно войти.'}];
    if(path === '/api/me') return [200, {pid:u.pid, email:u.email, admin:u.admin, role:u.role, code:u.code, name:u.name}];
    if(path === '/api/sync'){
      var since = +((url.match(/since=(\d+)/) || [])[1] || 0);
      var out = Object.keys(st.docs).filter(function(p){ return st.docs[p].ver > since; }).map(function(p){
        var d = get(p); return {path:p, data:d === null ? null : acl.readable(u, p, d, ps)};
      }).filter(function(d){ return (since && u.role !== 'employee') || d.data !== null; });
      return [200, {ver:st.ver, docs:out}];
    }
    if(path === '/api/doc'){
      var prev = get(b.path), next = b.op === 'delete' ? null : 'base' in b ? merge3(b.base === null ? undefined : b.base, b.data, prev === null ? undefined : prev) : b.data;
      if(next === undefined) next = null;
      var err = acl.writeError(u, b.path, prev, next, ps);
      if(err) return [403, {error:err}];
      return [200, {ver:put(b.path, next)}];
    }
    if(path === '/api/import-preboard' && u.admin){
      var ds = b.docs || {}, ok = Object.keys(ds).filter(function(p){ return acl.PATH_RE.test(p) && acl.isPreboard(p) && ds[p] && typeof ds[p] === 'object'; });
      if(!ok.length) return [400, {error:'В файле нет данных пребординга.'}];
      ok.forEach(function(p){ put(p, ds[p]); });
      return [200, {ok:true, docs:ok.length}];
    }
    return [404, {error:'Не найдено.'}];
  }
  var real = window.fetch.bind(window);
  window.fetch = function(url, o){
    if(typeof url !== 'string' || url.indexOf('/api/') !== 0) return real(url, o);
    o = o || {};
    var b = null; try{ b = o.body ? JSON.parse(o.body) : {}; }catch(e){ b = {}; }
    return Promise.resolve(handle(url, o.method || 'GET', b)).then(function(r){
      return new Response(JSON.stringify(r[1]), {status:r[0], headers:{'Content-Type':'application/json'}});
    });
  };
  window.iwayDemoFill = function(l){ document.getElementById('gateLogin').value = l; document.getElementById('gatePass').value = 'demo'; };
  window.iwayDemoReset = function(){ try{ sessionStorage.removeItem(KEY); }catch(e){} location.reload(); };
})();
</script>
"""
mock = mock.replace('ACL', acl).replace('MERGE', merge).replace('DOCS', json.dumps(docs, ensure_ascii=False))

hint = """
    <div class="demo-acc" id="demoAcc">
      <b>Демо: как это будет на iteamboard.ru.</b> Данные выдуманные, пароль у всех <code>demo</code>.
      <div class="demo-row">
        <button type="button" class="btn ghost" data-l="yulia">Юлия · администратор</button>
        <button type="button" class="btn ghost" data-l="shua@iway.ru">Анна · HR-менеджер</button>
        <button type="button" class="btn ghost" data-l="IW-DEMO">Мария · сотрудник</button>
      </div>
      <button type="button" class="demo-reset" id="demoReset">Сбросить демо-данные</button>
    </div>"""
css = """
  .demo-acc{margin-top:18px; padding:14px 16px; border:1px dashed var(--line-strong); border-radius:12px; font-size:13.5px; color:var(--ink-2); display:flex; flex-direction:column; gap:10px;}
  .demo-acc b{color:var(--ink);}
  .demo-row{display:flex; flex-wrap:wrap; gap:8px;}
  .demo-row .btn{font-size:13px;}
  .demo-reset{align-self:flex-start; background:none; border:0; padding:0; color:var(--ink-3); text-decoration:underline; cursor:pointer; font:inherit;}
</style>"""
wire = """
<script>
  document.querySelectorAll('#demoAcc [data-l]').forEach(function(b){ b.addEventListener('click', function(){ iwayDemoFill(b.getAttribute('data-l')); document.getElementById('gateForm').requestSubmit(); }); });
  document.getElementById('demoReset').addEventListener('click', iwayDemoReset);
</script>"""

def rep(s, a, b, n=1):
    assert s.count(a) == n, a
    return s.replace(a, b)
# метрики в демо — песочница метрик (на сервере они на /metrics в той же вкладке)
page = rep(page, "window.HR_SERVER ? '/metrics' :", "'https://claude.ai/artifact/LT73wVkVx9bYcwANYwPVt1' ||")
page = rep(page, "ext:!window.HR_SERVER,", "ext:true,")
# после входа сервер перезагружает страницу по адресу; у артефакта адрес с параметрами — перезагружаем как есть
page = rep(page, "location.replace(location.pathname);", "location.reload();")
page = rep(page, '<p class="gate-foot" id="gateFoot">', hint + '\n    <p class="gate-foot" id="gateFoot">')
page = re.sub(r'</style>', css, page, count=1)
page = rep(page, '<title>Корпоративный портал i’way</title>', '<title>Демо портала i’way</title>')
out.write_text(page.replace('<style>', mock + '<style>', 1) + wire, encoding='utf-8')
print(out, len(page) // 1024, 'КБ')
