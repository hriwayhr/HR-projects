/* эмуляция базы артефакта: data() возвращает ЗАМОРОЖЕННЫЕ объекты, как на платформе */
window.__store = {};
function freeze(o){
  if(o && typeof o === 'object'){ Object.keys(o).forEach(function(k){ freeze(o[k]); }); Object.freeze(o); }
  return o;
}
function snap(path){
  var d = window.__store[path];
  return {id: path.split('/').pop(), exists: !!d, data: function(){ return d ? freeze(JSON.parse(JSON.stringify(d))) : undefined; }};
}
function query(coll, filters){
  var out = Object.keys(window.__store).filter(function(p){
    return p.indexOf(coll + '/') === 0 && p.split('/').length === coll.split('/').length + 1;
  }).map(snap).filter(function(s){
    return filters.every(function(f){ return s.data()[f[0]] === f[2]; });
  });
  return Promise.resolve({docs: out, size: out.length, empty: !out.length});
}
window.__listeners = [];
function notify(){ window.__listeners.forEach(function(l){ query(l.coll, l.filters).then(l.cb); }); }
window.__notify = notify;
function collRef(coll, filters){
  filters = filters || [];
  return {
    where: function(f, op, v){ return collRef(coll, filters.concat([[f, op, v]])); },
    limit: function(){ return collRef(coll, filters); },
    get: function(){ return query(coll, filters); },
    doc: function(id){ return window.__db.doc(coll + '/' + (id || 'auto' + Math.random().toString(36).slice(2, 10))); },
    onSnapshot: function(next){
      var l = {coll: coll, filters: filters, cb: next};
      window.__listeners.push(l);
      query(coll, filters).then(next);
      return function(){ window.__listeners = window.__listeners.filter(function(x){ return x !== l; }); };
    }
  };
}
window.claude = { use: function(name){
  if(name === 'db') return Promise.resolve(window.__db = {
    doc: function(path){ return {
      id: path.split('/').pop(),
      get: function(){ return Promise.resolve(snap(path)); },
      onSnapshot: function(next){
        var l = {coll: path, filters: [], cb: function(){ next(snap(path)); }};
        window.__listeners.push(l); next(snap(path));
        return function(){ window.__listeners = window.__listeners.filter(function(x){ return x !== l; }); };
      },
      set: function(data){ window.__store[path] = JSON.parse(JSON.stringify(data)); notify(); return Promise.resolve(); },
      update: function(data){
        if(!window.__store[path]) return Promise.reject({code:'invalid_argument'});
        (function merge(t, s){ Object.keys(s).forEach(function(k){
          if(s[k] && typeof s[k] === 'object' && !Array.isArray(s[k]) && t[k] && typeof t[k] === 'object') merge(t[k], s[k]);
          else t[k] = JSON.parse(JSON.stringify(s[k]));
        }); })(window.__store[path], data);
        notify(); return Promise.resolve();
      },
      delete: function(){ delete window.__store[path]; notify(); return Promise.resolve(); }
    };},
    collection: function(coll){ return collRef(coll); }
  });
  if(name === 'user') return Promise.resolve({
    isOwner: function(){ return Promise.resolve(true); },
    canEdit: function(){ return Promise.resolve(true); }
  });
  return Promise.resolve(null);
}};
