'use strict';
window.Store=(function(){
let db;
async function open(){return new Promise((resolve,reject)=>{const r=indexedDB.open('portically-campo-energia-v1',1);r.onupgradeneeded=()=>{const d=r.result;['projects','visits','evidence','audit','meta'].forEach(s=>d.createObjectStore(s,{keyPath:'id'}));};r.onsuccess=()=>{db=r.result;db.onversionchange=()=>db.close();resolve(db);};r.onerror=()=>reject(r.error);r.onblocked=()=>reject(Error('Feche outras abas do aplicativo para atualizar o banco.'));});}
function get(store,key){return new Promise((resolve,reject)=>{let r=db.transaction(store).objectStore(store).get(key);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});}
function all(store){return new Promise((resolve,reject)=>{let r=db.transaction(store).objectStore(store).getAll();r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});}
function batch(ops){return new Promise((resolve,reject)=>{let tx;try{tx=db.transaction([...new Set(ops.map(x=>x.store))],'readwrite');for(const o of ops){let s=tx.objectStore(o.store);o.delete?s.delete(o.key):s.put(o.value);}}catch(e){reject(e);return;}tx.oncomplete=()=>resolve();tx.onerror=()=>reject(tx.error||Error('Falha ao salvar.'));tx.onabort=()=>reject(tx.error||Error('Gravação cancelada.'));});}
function put(store,value){return batch([{store,value}]);}
return {open,get,all,put,batch};
})();
