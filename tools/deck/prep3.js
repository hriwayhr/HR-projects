const sharp=require('sharp'),fs=require('fs');
const M='../src/x/ppt/media/',O='img/';
const DPI=150;
function leafSvg(w,h,v){ // asymmetric corners: v=0 big TR+BL, v=1 big TL+BR
  const R=Math.round(Math.min(w,h)*0.42), r=Math.round(Math.min(w,h)*0.07);
  const [tl,tr,br,bl]=v?[R,r,R,r]:[r,R,r,R];
  return `<svg width="${w}" height="${h}"><path d="M${tl},0 H${w-tr} A${tr},${tr} 0 0 1 ${w},${tr} V${h-br} A${br},${br} 0 0 1 ${w-br},${h} H${bl} A${bl},${bl} 0 0 1 0,${h-bl} V${tl} A${tl},${tl} 0 0 1 ${tl},0 Z" fill="#fff"/></svg>`;
}
const rrSvg=(w,h,r)=>`<svg width="${w}" height="${h}"><rect width="${w}" height="${h}" rx="${r}" ry="${r}" fill="#fff"/></svg>`;
async function shaped(src,out,wi,hi,mk,pos='centre'){
  const w=Math.round(wi*DPI),h=Math.round(hi*DPI);
  await sharp(M+src).resize(w,h,{fit:'cover',position:pos}).composite([{input:Buffer.from(mk(w,h)),blend:'dest-in'}]).png({compressionLevel:9}).toFile(O+out);
}
(async()=>{
 await shaped('image5.png','L_hero.png',5.43,4.7,(w,h)=>leafSvg(w,h,0),'right');
 await shaped('image7.jpg','L_julia.png',3.5,3.7,(w,h)=>leafSvg(w,h,0));
 await shaped('image8.jpg','L_anna.png',3.5,3.7,(w,h)=>leafSvg(w,h,1));
 await shaped('image9.jpg','L_elena.png',3.5,3.7,(w,h)=>leafSvg(w,h,0));
 await shaped('image13.jpeg','L_found.png',3.3,4.5,(w,h)=>leafSvg(w,h,1));
 await shaped('image10.png','L_team.png',5.6,4.9,(w,h)=>leafSvg(w,h,0));
 for (const [s,n] of [['image16.jpg','d1'],['image17.jpg','d2'],['image18.png','d3'],['image20.jpeg','d5']])
   await shaped(s,'R_'+n+'.png',2.85,4.0,(w,h)=>rrSvg(w,h,Math.round(0.3*DPI)),'north');
 await shaped('image15.png','R_dash.png',7.4,4.18,(w,h)=>rrSvg(w,h,Math.round(0.3*DPI)));
 await shaped('image22.jpeg','map.png',8.9,4.9,(w,h)=>rrSvg(w,h,Math.round(0.3*DPI)));
 console.log('ok');
})();
