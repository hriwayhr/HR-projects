"""Добавляет плавный переход (fade) и мягкое появление элементов (fade-in, группами) в каждый слайд.
usage: python3 anim.py in.pptx out.pptx"""
import sys, zipfile, re
from lxml import etree
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main', 'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
P = '{%s}' % NS['p']
EMU = 914400
FADE_MS, MAX_TOTAL_MS = 700, 3200

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
    step = min(350, MAX_TOTAL_MS // max(n, 1))
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

def process(xml_bytes):
    root = etree.fromstring(xml_bytes)
    tree = root.find('.//p:cSld/p:spTree', NS)
    groups, cur = [], None
    for el in tree:
        if el.tag not in (P + 'sp', P + 'pic', P + 'cxnSp', P + 'graphicFrame'): continue
        sid, box, ph, txbox = info(el)
        if ph is not None and ph.get('type') in ('sldNum', 'ftr', 'dt'): continue
        item = (sid, el.tag == P + 'sp', txbox)
        if is_container(el, box, txbox):
            groups.append([item]); cur = box
        elif el.tag == P + 'sp' and box is not None and not txbox and el.find('.//a:prstGeom', NS) is not None and el.find('.//a:prstGeom', NS).get('prst') == 'ellipse':
            groups.append([item]); cur = box   # бейдж: иконка внутри появляется вместе с кругом
        elif cur is not None and box is not None and inside(box, cur):
            groups[-1].append(item)
        else:
            groups.append([item]); cur = None
    for old in root.findall('p:transition', NS) + root.findall('p:timing', NS): root.remove(old)
    anchor = root.find('p:clrMapOvr', NS)
    trans = etree.fromstring(f'<p:transition xmlns:p="{NS["p"]}" spd="slow"><p:fade/></p:transition>')
    anchor.addnext(trans)
    if groups: trans.addnext(build_timing(groups))
    return etree.tostring(root, xml_declaration=True, encoding='UTF-8', standalone=True), len(groups)

src, dst = sys.argv[1], sys.argv[2]
zin = zipfile.ZipFile(src); zout = zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED)
for it in zin.infolist():
    d = zin.read(it.filename)
    if re.fullmatch(r'ppt/slides/slide\d+\.xml', it.filename):
        d, n = process(d); print(it.filename, n, 'groups')
    zout.writestr(it, d)
zout.close()
