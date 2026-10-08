const sharp=require('sharp');
const M='../src/x/ppt/media/',O='img/',DPI=150;
const rr=(w,h,r)=>Buffer.from(`<svg width="${w}" height="${h}"><rect width="${w}" height="${h}" rx="${r}" ry="${r}" fill="#fff"/></svg>`);
async function ph(src,out,wi,hi,r,pos='centre'){
  const w=Math.round(wi*DPI),h=Math.round(hi*DPI);
  await sharp(M+src).resize(w,h,{fit:'cover',position:pos}).composite([{input:rr(w,h,Math.round(r*DPI)),blend:'dest-in'}]).png({compressionLevel:9}).toFile(O+out);
}
async function face(src,out,wi,hi,r,fx,fy,sc){
  const m=await sharp(M+src).metadata();const ar=wi/hi;
  let cw=Math.min(m.width,m.height*ar)*sc, ch=cw/ar;
  let left=Math.round(Math.min(Math.max(fx*m.width-cw/2,0),m.width-cw)), top=Math.round(Math.min(Math.max(fy*m.height-ch/2,0),m.height-ch));
  const w=Math.round(wi*DPI),h=Math.round(hi*DPI);
  const buf=await sharp(M+src).extract({left,top,width:Math.round(cw),height:Math.round(ch)}).resize(w,h).toBuffer();
  await sharp(buf).composite([{input:rr(w,h,Math.round(r*DPI)),blend:'dest-in'}]).png({compressionLevel:9}).toFile(O+out);
}
(async()=>{
 await ph('image5.png','H_hero.png',5.3,6.1,0.3,'right');
 const att=sharp.strategy.attention;
 await face('image7.jpg','P_julia.png',3.35,2.5,0.2,0.5,0.36,0.85);
 await face('image8.jpg','P_anna.png',3.35,2.5,0.2,0.47,0.38,0.85);
 await face('image9.jpg','P_elena.png',3.35,2.5,0.2,0.72,0.38,0.78);
 await ph('image10.png','P_team.png',4.6,4.2,0.3);
 await ph('image13.jpeg','P_found.png',3.3,4.2,0.3);
 for (const [s,n] of [['image16.jpg','d1'],['image17.jpg','d2'],['image18.png','d3'],['image20.jpeg','d5']]) await ph(s,'P_'+n+'.png',2.5,2.9,0.2,'north');
 await ph('image15.png','P_dash.png',7.1,4.0,0.25);
 await ph('image22.jpeg','P_map.png',8.2,4.5,0.25);
 await face('image7.jpg','P_t1.png',2.3,2.3,0.3,0.5,0.36,0.8);
 await face('image8.jpg','P_t2.png',2.3,2.3,0.3,0.47,0.38,0.8);
 await face('image9.jpg','P_t3.png',2.3,2.3,0.3,0.72,0.38,0.78);
 console.log('ok');
})();
