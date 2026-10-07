import zipfile,re
o=zipfile.ZipFile('../src/orig.pptx')
rels=o.read('ppt/_rels/presentation.xml.rels').decode()
tg={}
for m in re.finditer(r'<Relationship [^>]*>',rels):
    t=m.group(0);i=re.search(r'Id="([^"]+)"',t).group(1);g=re.search(r'Target="([^"]+)"',t).group(1)
    if g.startswith('fonts/'):tg[i]=g
use=['rId30','rId31','rId32']
zin=zipfile.ZipFile('deck.pptx');zout=zipfile.ZipFile('out.pptx','w',zipfile.ZIP_DEFLATED)
for it in zin.infolist():
    d=zin.read(it.filename)
    if it.filename=='[Content_Types].xml':
        t=d.decode()
        if 'fntdata' not in t:t=t.replace('<Default ','<Default Extension="fntdata" ContentType="application/x-fontdata"/><Default ',1)
        d=t.encode()
    if it.filename=='ppt/_rels/presentation.xml.rels':
        add=''.join(f'<Relationship Id="rIdF{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/font" Target="{tg[r]}"/>' for i,r in enumerate(use))
        d=d.decode().replace('</Relationships>',add+'</Relationships>').encode()
    if it.filename=='ppt/presentation.xml':
        emb='<p:embeddedFontLst><p:embeddedFont><p:font typeface="Fedra Sans Pro (Основной текст)"/><p:regular r:id="rIdF0"/><p:bold r:id="rIdF1"/><p:italic r:id="rIdF2"/></p:embeddedFont></p:embeddedFontLst>'
        d=re.sub(r'(<p:notesSz[^>]*/>)',lambda m:m.group(1)+emb,d.decode(),count=1).encode()
    zout.writestr(it,d)
for r in use:zout.writestr('ppt/'+tg[r],o.read('ppt/'+tg[r]))
zout.close()
