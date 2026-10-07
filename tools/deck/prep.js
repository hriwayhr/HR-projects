const sharp=require('sharp'),fs=require('fs');
const M='../src/x/ppt/media/',O='img/';
const rr=(w,h,r)=>Buffer.from(`<svg width="${w}" height="${h}"><rect width="${w}" height="${h}" rx="${r}" ry="${r}" fill="#fff"/></svg>`);
async function ph(src,out,wi,hi,{pos='centre',r=0.18,dpi=150}={}){
  const w=Math.round(wi*dpi),h=Math.round(hi*dpi);
  let s=sharp(M+src).resize(w,h,{fit:'cover',position:pos});
  if(r>0) s=s.composite([{input:rr(w,h,Math.round(r*dpi)),blend:'dest-in'}]).png({compressionLevel:9,palette:false});
  else s=s.jpeg({quality:84});
  await s.toFile(O+out);
}
async function comma(color,out){
  let svg=fs.readFileSync(M+'image3.svg','utf8').replace(/fill="#00AD5A"/,`fill="${color}"`);
  const b=await sharp(Buffer.from(svg),{density:4500}).png().toBuffer();
  await sharp(b).trim().toFile(O+out);
}
(async()=>{
 await comma('#C9EDDA','comma_mint.png');await comma('#00AD5A','comma_green.png');await comma('#009634','comma_g.png');await comma('#FFFFFF','comma_white.png');await comma('#99DEBD','comma_m2.png');
 await sharp('../src/x/ppt/media/image1.svg',{density:500}).png().toFile(O+'logo.png');
 await ph('image5.png','agenda.png',6.2,7.5,{pos:'right',r:0});
 await ph('image7.jpg','p_julia.jpg',3,3,{r:0,dpi:200});
 await ph('image8.jpg','p_anna.jpg',3,3,{r:0,dpi:200});
 await ph('image9.jpg','p_elena.jpg',3,3,{r:0,dpi:200});
 await ph('image10.png','team.png',5.4,5.0,{r:0.25});
 await ph('image13.jpeg','founders.png',4.9,7.5,{r:0,pos:'centre'});
 await ph('image15.png','dash.png',7.2,4.07,{r:0.2});
 await ph('image22.jpeg','map.png',8.9,4.9,{r:0.2,dpi:160});
 await ph('image16.jpg','d1.png',2.46,2.9,{pos:'north',r:0.2});
 await ph('image17.jpg','d2.png',2.46,2.9,{pos:'north',r:0.2});
 await ph('image18.png','d3.png',2.46,2.9,{pos:'north',r:0.2});
 await ph('image20.jpeg','d5.png',2.46,2.9,{pos:'north',r:0.2});
 const m=await sharp(O+'comma_mint.png').metadata();console.log(m.width,m.height);
})();
