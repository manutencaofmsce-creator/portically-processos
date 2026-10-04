/* Funções puras e ZIP STORE: sem dependências de rede. */
'use strict';
(function(root){
const R=6371008.8, rad=x=>x*Math.PI/180;
function valid(p){return p && Number.isFinite(p.lat)&&Number.isFinite(p.lon)&&Math.abs(p.lat)<=85&&Math.abs(p.lon)<=180;}
function distance(a,b){const x=rad(b.lat-a.lat),y=rad(b.lon-a.lon);const h=Math.sin(x/2)**2+Math.cos(rad(a.lat))*Math.cos(rad(b.lat))*Math.sin(y/2)**2;return 2*R*Math.atan2(Math.sqrt(h),Math.sqrt(Math.max(0,1-h)));}
function project(p,c){return {x:R*rad(p.lon-c.lon)*Math.cos(rad(c.lat)),y:R*rad(p.lat-c.lat)};}
function unproject(p,c){return {lat:c.lat+p.y/R*180/Math.PI,lon:c.lon+p.x/(R*Math.cos(rad(c.lat)))*180/Math.PI};}
function square(c,ha){const s=Math.sqrt(ha*10000)/2;return [[-s,-s],[s,-s],[s,s],[-s,s]].map(([x,y])=>unproject({x,y},c));}
function crosses(a,b,c,d){const cr=(p,q,r)=>(q.x-p.x)*(r.y-p.y)-(q.y-p.y)*(r.x-p.x),eps=1e-7;
const on=(p,q,r)=>Math.abs(cr(p,q,r))<eps && r.x>=Math.min(p.x,q.x)-eps&&r.x<=Math.max(p.x,q.x)+eps&&r.y>=Math.min(p.y,q.y)-eps&&r.y<=Math.max(p.y,q.y)+eps;
const u=cr(a,b,c),v=cr(a,b,d),w=cr(c,d,a),z=cr(c,d,b);return ((u>eps&&v< -eps)||(u< -eps&&v>eps))&&((w>eps&&z< -eps)||(w< -eps&&z>eps))||on(a,b,c)||on(a,b,d)||on(c,d,a)||on(c,d,b);}
function polygon(points,closed=true){
 if(points.some(p=>!valid(p)))return {error:'Coordenadas inválidas.'};
 if(points.length<3)return {error:'Registre ao menos três vértices distintos.'};
 const c={lat:points.reduce((s,p)=>s+p.lat,0)/points.length,lon:points.reduce((s,p)=>s+p.lon,0)/points.length},ps=points.map(p=>project(p,c));
 if(ps.some(p=>Math.hypot(p.x,p.y)>100000))return {error:'Polígono muito extenso para esta estimativa local (100 km).'};
 for(let i=0;i<ps.length;i++)for(let j=i+1;j<ps.length;j++)if(distance(points[i],points[j])<0.05)return {error:'Há vértices repetidos. Revise antes de fechar.'};
 let twice=0,perimeter=0;for(let i=0;i<ps.length;i++){const j=(i+1)%ps.length;twice+=ps[i].x*ps[j].y-ps[j].x*ps[i].y;if(closed||i<ps.length-1)perimeter+=distance(points[i],points[j]);}
 for(let i=0;i<ps.length;i++)for(let j=i+1;j<ps.length;j++){if(j===i+1||(i===0&&j===ps.length-1))continue;if(crosses(ps[i],ps[(i+1)%ps.length],ps[j],ps[(j+1)%ps.length]))return {error:'Os limites se cruzam ou encostam indevidamente. Revise a ordem dos vértices.'};}
 if(Math.abs(twice)<0.1)return {error:'Os vértices não formam uma área válida.'};
 return {ha:closed?Math.abs(twice)/2/10000:null,perimeter,approximate:true};
}
function parseGeoJSON(data){let g=data;if(g.type==='FeatureCollection'){const a=g.features.filter(f=>f.geometry&&f.geometry.type==='Polygon');if(a.length!==1)throw Error('Use um GeoJSON com exatamente um Polygon.');g=a[0].geometry;}else if(g.type==='Feature')g=g.geometry;
 if(!g||g.type!=='Polygon'||g.coordinates.length!==1)throw Error('Importe um único Polygon, sem áreas internas excluídas. MultiPolygon e furos precisam de tratamento técnico.');
 let ps=g.coordinates[0].map(c=>({lat:Number(c[1]),lon:Number(c[0])}));if(ps.length>1&&distance(ps[0],ps[ps.length-1])<0.05)ps.pop();if(ps.length>3000)throw Error('Limite de 3.000 vértices por importação.');const check=polygon(ps);if(check.error)throw Error(check.error);return ps;
}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function csvCell(v){let s=String(v??'');if(typeof v!=='number'&&/^[=+@\-\t\r]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';}
function csv(rows){return '\uFEFF'+rows.map(row=>row.map(csvCell).join(';')).join('\r\n');}
const table=Uint32Array.from({length:256},(_,n)=>{for(let i=0;i<8;i++)n=n&1?0xedb88320^(n>>>1):n>>>1;return n>>>0;});
function crc32(bytes){let n=0xffffffff;for(const b of bytes)n=table[(n^b)&255]^(n>>>8);return (n^0xffffffff)>>>0;}
function bin(n){let b=new Uint8Array(n);return [b,new DataView(b.buffer)];}
async function zip(entries){let pieces=[],central=[],offset=0;const enc=new TextEncoder();let now=new Date();let time=now.getHours()<<11|now.getMinutes()<<5|now.getSeconds()>>1,date=Math.max(0,now.getFullYear()-1980)<<9|(now.getMonth()+1)<<5|now.getDate();
 for(const item of entries){const name=enc.encode(item.name);let data=item.data instanceof Uint8Array?item.data:new Uint8Array(await (item.data instanceof Blob?item.data:new Blob([item.data])).arrayBuffer());const crc=crc32(data);let [h,v]=bin(30);v.setUint32(0,0x04034b50,true);v.setUint16(4,20,true);v.setUint16(6,0x800,true);v.setUint16(10,time,true);v.setUint16(12,date,true);v.setUint32(14,crc,true);v.setUint32(18,data.length,true);v.setUint32(22,data.length,true);v.setUint16(26,name.length,true);pieces.push(h,name,data);
 let [c,w]=bin(46);w.setUint32(0,0x02014b50,true);w.setUint16(4,20,true);w.setUint16(6,20,true);w.setUint16(8,0x800,true);w.setUint16(12,time,true);w.setUint16(14,date,true);w.setUint32(16,crc,true);w.setUint32(20,data.length,true);w.setUint32(24,data.length,true);w.setUint16(28,name.length,true);w.setUint32(42,offset,true);central.push(c,name);offset+=30+name.length+data.length;
 }
 const csize=central.reduce((n,c)=>n+c.length,0);let [end,v]=bin(22);v.setUint32(0,0x06054b50,true);v.setUint16(8,entries.length,true);v.setUint16(10,entries.length,true);v.setUint32(12,csize,true);v.setUint32(16,offset,true);return new Blob([...pieces,...central,end],{type:'application/zip'});
}
function unzip(buffer){const b=new Uint8Array(buffer),v=new DataView(buffer),out=new Map(),dec=new TextDecoder();let end=-1;for(let i=b.length-22;i>=Math.max(0,b.length-65557);i--)if(v.getUint32(i,true)===0x06054b50){end=i;break;}if(end<0)throw Error('ZIP inválido.');let count=v.getUint16(end+10,true),pos=v.getUint32(end+16,true);if(count>6000)throw Error('Quantidade de arquivos acima do limite.');
 for(let i=0;i<count;i++){if(pos+46>b.length||v.getUint32(pos,true)!==0x02014b50)throw Error('Diretório ZIP inválido.');let method=v.getUint16(pos+10,true),crc=v.getUint32(pos+16,true),size=v.getUint32(pos+20,true),n=v.getUint16(pos+28,true),e=v.getUint16(pos+30,true),c=v.getUint16(pos+32,true),loc=v.getUint32(pos+42,true);if(method!==0)throw Error('Restaure o ZIP original, sem recomprimir: esta V2 importa ZIP STORE gerado pelo app.');let name=dec.decode(b.subarray(pos+46,pos+46+n));if(name.includes('..')||name.startsWith('/')||name.includes('\\')||out.has(name))throw Error('Nome de arquivo inválido/duplicado no ZIP.');if(loc+30>b.length||v.getUint32(loc,true)!==0x04034b50)throw Error('Entrada ZIP inválida.');let start=loc+30+v.getUint16(loc+26,true)+v.getUint16(loc+28,true);if(start+size>b.length)throw Error('ZIP incompleto.');let data=b.slice(start,start+size);if(crc32(data)!==crc)throw Error('Integridade CRC inválida: '+name);out.set(name,data);pos+=46+n+e+c;}
 return out;
}
const obj={R,valid,distance,project,unproject,square,polygon,parseGeoJSON,esc,csv,crc32,zip,unzip};root.Core=obj;if(typeof module!=='undefined')module.exports=obj;
})(typeof window!=='undefined'?window:globalThis);
