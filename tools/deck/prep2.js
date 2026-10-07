const sharp=require('sharp');
const M='../src/x/ppt/media/',O='img/';
async function commaPhoto(src,out,wi,hi,{pos='centre',dpi=150,flip=false}={}){
  const w=Math.round(wi*dpi),h=Math.round(hi*dpi);
  const mask=await sharp(O+'comma_mint.png').resize(w,h,{fit:'fill'}).png().toBuffer();
  await sharp(M+src).resize(w,h,{fit:'cover',position:pos}).composite([{input:mask,blend:'dest-in'}]).png({compressionLevel:9}).toFile(O+out);
}
async function rect(src,out,wi,hi,{pos='north',dpi=150}={}){
  await sharp(M+src).resize(Math.round(wi*dpi),Math.round(hi*dpi),{fit:'cover',position:pos}).jpeg({quality:85}).toFile(O+out);
}
(async()=>{
 await commaPhoto('image5.png','c_hero.png',6.0,7.6,{pos:'right',dpi:130});
 await commaPhoto('image7.jpg','c_julia.png',3.3,4.17,{dpi:140});
 await commaPhoto('image8.jpg','c_anna.png',3.3,4.17,{dpi:140});
 await commaPhoto('image9.jpg','c_elena.png',3.3,4.17,{dpi:140});
 await commaPhoto('image13.jpeg','c_founders.png',4.3,5.44,{pos:'centre',dpi:140});
 for (const [s,n] of [['image16.jpg','D1'],['image17.jpg','D2'],['image18.png','D3'],['image20.jpeg','D5']]) await rect(s,n+'.jpg',3.333,3.75);
 await rect('image10.png','team_full.jpg',6.4,7.5,{pos:'centre'});
 console.log('ok');
})();
