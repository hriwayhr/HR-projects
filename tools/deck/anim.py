"""Добавляет плавный переход (fade) и мягкое появление элементов (fade-in, группами) в каждый слайд.
usage: python3 anim.py in.pptx out.pptx [slides_without_animation e.g. 1,3,10]"""
import sys, zipfile, re
from lxml import etree
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main', 'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
P = '{%s}' % NS['p']
EMU = 914400
FADE_MS = 900

def info(el):
    nv = el.find('.//p:cNvPr', NS)
    sid = int(nv.get('id'))
    xf = el.find('.//a:xfrm', NS)
    box = None
    if xf is not None and xf.find('a:off', NS) is not None:
        o, e = xf.find('a:off', NS), xf.find('a:ext', NS)
        box = (int(o.get('x')), int(o.get('y')), int(e.get('cx')), int(e.get('cy')))
    ph = el.find('.//p:nvPr/p:ph', NS)
    cnv = el.find('.//p:cNvSpPr', NS)
    txbox = cnv is not None and cnv.get('txBox') == '1'
    return sid, box, ph, txbox

def is_container(el, box, txbox):
    if el.tag != P + 'sp' or box is None or txbox: return False
    geom = el.find('.//a:prstGeom', NS)
    return geom is not None and geom.get('prst') in ('roundRect', 'rect') and box[2] >= 1.4 * EMU and box[3] >= 0.9 * EMU

def inside(box, outer):
    cx, cy = box[0] + box[2] / 2, box[1] + box[3] / 2
    return outer[0] <= cx <= outer[0] + outer[2] and outer[1] <= cy <= outer[1] + outer[3]

def build_timing(groups):
    n = len(groups)
    step = 0
    cid = [3]
    def nid():
        cid[0] += 1; return cid[0]
    effects, bld = [], []
    for gi, g in enumerate(groups):
        delay = gi * step
        for k, (sid, is_sp, txbox) in enumerate(g):
            first = gi == 0 and k == 0
            a, b, c = nid(), nid(), nid()
            grp = ' grpId="0"' if is_sp else ''
            effects.append(
                f'<p:par><p:cTn id="{a}" presetID="10" presetClass="entr" presetSubtype="0" fill="hold"{grp} nodeType="{"afterEffect" if first else "withEffect"}">'
                f'<p:stCondLst><p:cond delay="{delay}"/></p:stCondLst><p:childTnLst>'
                f'<p:set><p:cBhvr><p:cTn id="{b}" dur="1" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
                f'<p:tgtEl><p:spTgt spid="{sid}"/></p:tgtEl><p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>'
                f'<p:to><p:strVal val="visible"/></p:to></p:set>'
                f'<p:animEffect transition="in" filter="fade"><p:cBhvr><p:cTn id="{c}" dur="{FADE_MS}"/><p:tgtEl><p:spTgt spid="{sid}"/></p:tgtEl></p:cBhvr></p:animEffect>'
                f'</p:childTnLst></p:cTn></p:par>')
            if is_sp: bld.append(f'<p:bldP spid="{sid}" grpId="0"' + ('' if txbox else ' animBg="1"') + '/>')
    xml = (f'<p:timing xmlns:p="{NS["p"]}"><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
           f'<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
           f'<p:par><p:cTn id="3" fill="hold"><p:stCondLst><p:cond delay="indefinite"/><p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond></p:stCondLst><p:childTnLst>'
           f'<p:par><p:cTn id="{nid()}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
           + ''.join(effects) +
           '</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn>'
           '<p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
           '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq></p:childTnLst></p:cTn></p:par></p:tnLst>'
           + (f'<p:bldLst>{"".join(bld)}</p:bldLst>' if bld else '') + '</p:timing>')
    return etree.fromstring(xml)

def process(xml_bytes, animate):
    """Переход fade — на всех слайдах. Анимация (если animate): основной блок слайда появляется ОДНИМ мягким fade-in,
    шапка (тег, заголовок, вступление) и логотип остаются на месте."""
    root = etree.fromstring(xml_bytes)
    tree = root.find('.//p:cSld/p:spTree', NS)
    body, boxes = [], []
    for el in tree:
        if el.tag not in (P + 'sp', P + 'pic', P + 'cxnSp', P + 'graphicFrame'): continue
        sid, box, ph, txbox = info(el)
        if ph is not None: continue                      # заголовок и служебные плейсхолдеры
        if box is None or box[1] + box[3] <= 2.8 * EMU: continue   # шапка и логотип сверху
        body.append(el); boxes.append(box)
    gid = None
    if animate and body:
        # один объект-группа вместо эффекта на каждый элемент: в панели анимации будет ровно одна строка
        x0 = min(b[0] for b in boxes); y0 = min(b[1] for b in boxes)
        x1 = max(b[0] + b[2] for b in boxes); y1 = max(b[1] + b[3] for b in boxes)
        gid = max(int(e.get('id')) for e in tree.iter(P + 'cNvPr')) + 1
        grp = etree.fromstring(
            f'<p:grpSp xmlns:p="{NS["p"]}" xmlns:a="{NS["a"]}"><p:nvGrpSpPr><p:cNvPr id="{gid}" name="Основной блок"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            f'<p:grpSpPr><a:xfrm><a:off x="{x0}" y="{y0}"/><a:ext cx="{x1-x0}" cy="{y1-y0}"/><a:chOff x="{x0}" y="{y0}"/><a:chExt cx="{x1-x0}" cy="{y1-y0}"/></a:xfrm></p:grpSpPr></p:grpSp>')
        body[0].addprevious(grp)
        for el in body: grp.append(el)
    for old in root.findall('p:transition', NS) + root.findall('p:timing', NS): root.remove(old)
    anchor = root.find('p:clrMapOvr', NS)
    trans = etree.fromstring(f'<p:transition xmlns:p="{NS["p"]}" spd="slow"><p:fade/></p:transition>')
    anchor.addnext(trans)
    if gid: trans.addnext(build_timing([[(gid, False, False)]]))
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True), len(body)

src, dst = sys.argv[1], sys.argv[2]
skip = {int(x) for x in sys.argv[3].split(',')} if len(sys.argv) > 3 and sys.argv[3] else set()
zin = zipfile.ZipFile(src); zout = zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED)
for it in zin.infolist():
    d = zin.read(it.filename)
    m = re.fullmatch(r'ppt/slides/slide(\d+)\.xml', it.filename)
    if m:
        d, n = process(d, int(m.group(1)) not in skip); print(it.filename, 'static' if int(m.group(1)) in skip else f'fade body ({n} shapes)')
    zout.writestr(it, d)
zout.close()
