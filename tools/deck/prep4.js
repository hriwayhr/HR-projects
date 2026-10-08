const sharp=require('sharp');
const M='../src/x/ppt/media/',O='img/',DPI=150;
const rr=(w,h,r)=>Buffer.from(`<svg width="${w}" height="${h}"><rect width="${w}" height="${h}" rx="${r}" ry="${r}" fill="#fff"/></svg>`);
async function ph(src,out,wi,hi,r,pos='centre'){
  const w=Math.round(wi*DPI),h=Math.round(hi*DPI);
  await sharp(M+src).resize(w,h,{fit:'cover',position:pos}).composite([{input:rr(w,h,Math.round(r*DPI)),blend:'dest-in'}]).png({compressionLevel:9}).toFile(O+out);
}
(async()=>{
 await ph('image5.png','H_hero.png',5.3,6.1,0.3,'right');
 const att=sharp.strategy.attention;
 await ph('image7.jpg','P_julia.png',3.35,2.0,0.2,att);
 await ph('image8.jpg','P_anna.png',3.35,2.0,0.2,att);
 await ph('image9.jpg','P_elena.png',3.35,2.0,0.2,att);
 await ph('image10.png','P_team.png',4.6,4.2,0.3);
 await ph('image13.jpeg','P_found.png',3.3,4.2,0.3);
 for (const [s,n] of [['image16.jpg','d1'],['image17.jpg','d2'],['image18.png','d3'],['image20.jpeg','d5']]) await ph(s,'P_'+n+'.png',2.5,2.9,0.2,'north');
 await ph('image15.png','P_dash.png',7.1,4.0,0.25);
 await ph('image22.jpeg','P_map.png',8.2,4.5,0.25);
 for (const [s,n] of [['image7.jpg','t1'],['image8.jpg','t2'],['image9.jpg','t3']]) await ph(s,'P_'+n+'.png',2.3,2.3,0.3,att);
 console.log('ok');
})();
