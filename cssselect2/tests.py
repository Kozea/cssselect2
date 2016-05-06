# coding: utf8
"""
    cssselect2.tests
    ----------------

    Test suite for cssselect2.

    :copyright: (c) 2012 by Simon Sapin.
    :license: BSD, see LICENSE for more details.

"""

from . import compile_selector_list, ElementWrapper, SelectorError

import json
import os.path
import xml.etree.ElementTree as etree

import pytest


def resource(filename):
    return os.path.join(os.path.dirname(__file__), 'tests', filename)


def load_json(filename):
    return json.load(open(resource(filename)))


def get_test_document():
    document = etree.parse(resource('content.xhtml'))
    parent = next(e for e in document.getiterator() if e.get('id') == 'root')

    # Setup namespace tests
    for id in ('any-namespace', 'no-namespace'):
        div = etree.SubElement(parent, '{http://www.w3.org/1999/xhtml}div')
        div.set('id', id)
        etree.SubElement(div, '{http://www.w3.org/1999/xhtml}div') \
            .set('id', id + '-div1')
        etree.SubElement(div, '{http://www.w3.org/1999/xhtml}div') \
            .set('id', id + '-div2')
        etree.SubElement(div, 'div').set('id', id + '-div3')
        etree.SubElement(div, '{http://www.example.org/ns}div') \
            .set('id', id + '-div4')

    return document


TEST_DOCUMENT = get_test_document()


@pytest.mark.parametrize('test', load_json('invalid_selectors.json'))
def test_invalid_selectors(test):
    if test.get('xfail'):
        pytest.xfail()
    try:
        compile_selector_list(test['selector'])
    except SelectorError:
        pass
    else:
        raise AssertionError('Should be invalid: %(selector)r %(name)s' % test)


@pytest.mark.parametrize('test', load_json('valid_selectors.json'))
def test_valid_selectors(test):
    if test.get('xfail'):
        pytest.xfail()
    exclude = test.get('exclude', ())
    if 'document' in exclude or 'xhtml' in exclude:
        return
    root = ElementWrapper.from_xml_root(TEST_DOCUMENT)
    result = [e.id for e in root.query_all(test['selector'])]
    if result != test['expect']:
        print(test['selector'])
        print(result)
        print('!=')
        print(test['expect'])
        raise AssertionError(test['name'])


def test_select():
    root = etree.fromstring(HTML_IDS)

    def select_ids(selector, html_only):
        xml_ids = [element.get_attr('id', 'nil') for element in
                   ElementWrapper.from_xml_root(root).query_all(selector)]
        html_ids = [element.get_attr('id', 'nil') for element in
                    ElementWrapper.from_html_root(root).query_all(selector)]
        if html_only:
            assert xml_ids == []
        else:
            assert xml_ids == html_ids
        return html_ids

    def pcss(main, *selectors, **kwargs):
        html_only = kwargs.pop('html_only', False)
        result = select_ids(main, html_only)
        for selector in selectors:
            assert select_ids(selector, html_only) == result
        return result

    all_ids = pcss('*')
    assert all_ids[:6] == [
        'html', 'nil', 'link-href', 'link-nohref', 'nil', 'outer-div']
    assert all_ids[-1:] == ['foobar-span']
    assert pcss('div') == ['outer-div', 'li-div', 'foobar-div']
    assert pcss('DIV', html_only=True) == [
        'outer-div', 'li-div', 'foobar-div']  # case-insensitive in HTML
    assert pcss('div div') == ['li-div']
    assert pcss('div, div div') == ['outer-div', 'li-div', 'foobar-div']
    assert pcss('div , div div') == ['outer-div', 'li-div', 'foobar-div']
    assert pcss('a[name]') == ['name-anchor']
    assert pcss('a[NAme]', html_only=True) == [
        'name-anchor'] # case-insensitive in HTML:
    assert pcss('a[rel]') == ['tag-anchor', 'nofollow-anchor']
    assert pcss('a[rel="tag"]') == ['tag-anchor']
    assert pcss('a[href*="localhost"]') == ['tag-anchor']
    assert pcss('a[href*=""]') == []
    assert pcss('a[href^="http"]') == ['tag-anchor', 'nofollow-anchor']
    assert pcss('a[href^="http:"]') == ['tag-anchor']
    assert pcss('a[href^=""]') == []
    assert pcss('a[href$="org"]') == ['nofollow-anchor']
    assert pcss('a[href$=""]') == []
    assert pcss('div[foobar~="bc"]', 'div[foobar~="cde"]') == [
        'foobar-div']
    assert pcss('[foobar~="ab bc"]',
                '[foobar~=""]', '[foobar~=" \t"]') == []
    assert pcss('div[foobar~="cd"]') == []
    assert pcss('*[lang|="En"]', '[lang|="En-us"]') == ['second-li']
    # Attribute values are case sensitive
    assert pcss('*[lang|="en"]', '[lang|="en-US"]') == []
    assert pcss('*[lang|="e"]') == []
    # ... :lang() is not.
    assert pcss(
        ':lang(EN)', '*:lang(en-US)'
        ':lang(En)'
    ) == ['second-li', 'li-div']
    assert pcss(':lang(e)'#, html_only=True
    ) == []
    assert pcss('li:nth-child(3)') == ['third-li']
    assert pcss('li:nth-child(10)') == []
    assert pcss('li:nth-child(2n)', 'li:nth-child(even)',
                'li:nth-child(2n+0)') == [
        'second-li', 'fourth-li', 'sixth-li']
    assert pcss('li:nth-child(+2n+1)', 'li:nth-child(odd)') == [
        'first-li', 'third-li', 'fifth-li', 'seventh-li']
    assert pcss('li:nth-child(2n+4)') == ['fourth-li', 'sixth-li']
    assert pcss('li:nth-child(3n+1)') == [
        'first-li', 'fourth-li', 'seventh-li']
    assert pcss('li:nth-last-child(1)') == ['seventh-li']
    assert pcss('li:nth-last-child(0)') == []
    assert pcss('li:nth-last-child(2n+2)', 'li:nth-last-child(even)') == [
        'second-li', 'fourth-li', 'sixth-li']
    assert pcss('li:nth-last-child(2n+4)') == ['second-li', 'fourth-li']
    assert pcss('ol:first-of-type') == ['first-ol']
    assert pcss('ol:nth-child(1)') == []
    assert pcss('ol:nth-of-type(2)') == ['second-ol']
    assert pcss('ol:nth-last-of-type(2)') == ['first-ol']
    assert pcss('span:only-child') == ['foobar-span']
    assert pcss('div:only-child') == ['li-div']
    assert pcss('div *:only-child') == ['li-div', 'foobar-span']
    assert pcss('p *:only-of-type') == ['p-em', 'fieldset']
    assert pcss('p:only-of-type') == ['paragraph']
    assert pcss('a:empty', 'a:EMpty') == ['name-anchor']
    assert pcss('li:empty') == [
        'third-li', 'fourth-li', 'fifth-li', 'sixth-li']
    assert pcss(':root', 'html:root') == ['html']
    assert pcss('li:root', '* :root') == []
    assert pcss('.a', '.b', '*.a', 'ol.a') == ['first-ol']
    assert pcss('.c', '*.c') == ['first-ol', 'third-li', 'fourth-li']
    assert pcss('ol *.c', 'ol li.c', 'li ~ li.c', 'ol > li.c') == [
        'third-li', 'fourth-li']
    assert pcss('#first-li', 'li#first-li', '*#first-li') == ['first-li']
    assert pcss('li div', 'li > div', 'div div') == ['li-div']
    assert pcss('div > div') == []
    assert pcss('div>.c', 'div > .c') == ['first-ol']
    assert pcss('div + div') == ['foobar-div']
    assert pcss('a ~ a') == ['tag-anchor', 'nofollow-anchor']
    assert pcss('a[rel="tag"] ~ a') == ['nofollow-anchor']
    assert pcss('ol#first-ol li:last-child') == ['seventh-li']
    assert pcss('ol#first-ol *:last-child') == ['li-div', 'seventh-li']
    assert pcss('#outer-div:first-child') == ['outer-div']
    assert pcss('#outer-div :first-child') == [
        'name-anchor', 'first-li', 'li-div', 'p-b',
        'checkbox-fieldset-disabled', 'area-href']
    assert pcss('a[href]') == ['tag-anchor', 'nofollow-anchor']
    assert pcss(':not(*)') == []
    assert pcss('a:not([href])') == ['name-anchor']
    assert pcss('ol :Not([class])') == [
        'first-li', 'second-li', 'li-div',
        'fifth-li', 'sixth-li', 'seventh-li']
    # Invalid characters in XPath element names, should not crash
    assert pcss(r'di\a0 v', r'div\[') == []
    assert pcss(r'[h\a0 ref]', r'[h\]ref]') == []

    assert pcss(':link') == [
        'link-href', 'tag-anchor', 'nofollow-anchor', 'area-href']
    assert pcss(':visited') == []
    assert pcss(':enabled') == [
        'link-href', 'tag-anchor', 'nofollow-anchor',
        'checkbox-unchecked', 'text-checked', 'input-hidden',
        'checkbox-checked', 'area-href']
    assert pcss(':disabled') == [
        'checkbox-disabled', 'input-hidden-disabled',
        'checkbox-disabled-checked', 'fieldset',
        'checkbox-fieldset-disabled',
        'hidden-fieldset-disabled']
    assert pcss(':checked') == [
        'checkbox-checked', 'checkbox-disabled-checked']


def test_select_shakespeare():
    document = etree.fromstring(HTML_SHAKESPEARE)
    body = document.find('.//{http://www.w3.org/1999/xhtml}body')
    body = ElementWrapper.from_xml_root(body)

    def count(selector):
        return sum(1 for _ in body.query_all(selector))

    # Data borrowed from http://mootools.net/slickspeed/

    ## Changed from original; probably because I'm only
    ## searching the body.
    #assert count('*') == 252
    assert count('*') == 246
#    assert count('div:contains(CELIA)') == 26
    assert count('div:only-child') == 22 # ?
    assert count('div:nth-child(even)') == 106
    assert count('div:nth-child(2n)') == 106
    assert count('div:nth-child(odd)') == 137
    assert count('div:nth-child(2n+1)') == 137
    assert count('div:nth-child(n)') == 243
    assert count('div:last-child') == 53
    assert count('div:first-child') == 51
    assert count('div > div') == 242
    assert count('div + div') == 190
    assert count('div ~ div') == 190
    assert count('body') == 1
    assert count('body div') == 243
    assert count('div') == 243
    assert count('div div') == 242
    assert count('div div div') == 241
    assert count('div, div, div') == 243
    assert count('div, a, span') == 243
    assert count('.dialog') == 51
    assert count('div.dialog') == 51
    assert count('div .dialog') == 51
    assert count('div.character, div.dialog') == 99
    assert count('div.direction.dialog') == 0
    assert count('div.dialog.direction') == 0
    assert count('div.dialog.scene') == 1
    assert count('div.scene.scene') == 1
    assert count('div.scene .scene') == 0
    assert count('div.direction .dialog ') == 0
    assert count('div .dialog .direction') == 4
    assert count('div.dialog .dialog .direction') == 4
    assert count('#speech5') == 1
    assert count('div#speech5') == 1
    assert count('div #speech5') == 1
    assert count('div.scene div.dialog') == 49
    assert count('div#scene1 div.dialog div') == 142
    assert count('#scene1 #speech1') == 1
    assert count('div[class]') == 103
    assert count('div[class=dialog]') == 50
    assert count('div[class^=dia]') == 51
    assert count('div[class$=log]') == 50
    assert count('div[class*=sce]') == 1
    assert count('div[class|=dialog]') == 50 # ? Seems right
#    assert count('div[class!=madeup]') == 243 # ? Seems right
    assert count('div[class~=dialog]') == 51 # ? Seems right
    assert count('div:match(CELIA)') == 26
    assert count('div:match(^CELIA)') == 21

HTML_IDS = '''
<html id="html" xmlns="http://www.w3.org/1999/xhtml"><head>
  <link id="link-href" href="foo" />
  <link id="link-nohref" />
</head><body>
<div id="outer-div">
 <a id="name-anchor" name="foo"></a>
 <a id="tag-anchor" rel="tag" href="http://localhost/foo">link</a>
 <a id="nofollow-anchor" rel="nofollow" href="https://example.org">
    link</a>
 <ol id="first-ol" class="a b c">
   <li id="first-li">content</li>
   <li id="second-li" lang="En-us">
     <div id="li-div">
     </div>
   </li>
   <li id="third-li" class="ab c"></li>
   <li id="fourth-li" class="ab
c"></li>
   <li id="fifth-li"></li>
   <li id="sixth-li"></li>
   <li id="seventh-li">  </li>
 </ol>
 <p id="paragraph">
   <b id="p-b">hi</b> <em id="p-em">there</em>
   <b id="p-b2">guy</b>
   <input type="checkbox" id="checkbox-unchecked" />
   <input type="checkbox" id="checkbox-disabled" disabled="" />
   <input type="text" id="text-checked" checked="checked" />
   <input type="hidden" id="input-hidden" />
   <input type="hidden" id="input-hidden-disabled" disabled="disabled" />
   <input type="checkbox" id="checkbox-checked" checked="checked" />
   <input type="checkbox" id="checkbox-disabled-checked"
          disabled="disabled" checked="checked" />
   <fieldset id="fieldset" disabled="disabled">
     <input type="checkbox" id="checkbox-fieldset-disabled" />
     <input type="hidden" id="hidden-fieldset-disabled" />
   </fieldset>
 </p>
 <ol id="second-ol">
 </ol>
 <map name="dummymap">
   <area shape="circle" coords="200,250,25" href="foo.html" id="area-href" />
   <area shape="default" id="area-nohref" />
 </map>
</div>
<div id="foobar-div" foobar="ab bc
cde"><span id="foobar-span"></span></div>
</body></html>
'''


HTML_SHAKESPEARE = '''
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Strict//EN"
	"http://www.w3.org/TR/xhtml1/DTD/xhtml1-strict.dtd">
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en" lang="en" debug="true">
<head>
	<meta http-equiv="Content-Type" content="text/html; charset=utf-8"/>
</head>
<body>
	<div id="test">
	<div class="dialog">
	<h2>As You Like It</h2>
	<div id="playwright">
	  by William Shakespeare
	</div>
	<div class="dialog scene thirdClass" id="scene1">
	  <h3>ACT I, SCENE III. A room in the palace.</h3>
	  <div class="dialog">
	  <div class="direction">Enter CELIA and ROSALIND</div>
	  </div>
	  <div id="speech1" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.1">Why, cousin! why, Rosalind! Cupid have mercy! not a word?</div>
	  </div>
	  <div id="speech2" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.2">Not one to throw at a dog.</div>
	  </div>
	  <div id="speech3" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.3">No, thy words are too precious to be cast away upon</div>
	  <div id="scene1.3.4">curs; throw some of them at me; come, lame me with reasons.</div>
	  </div>
	  <div id="speech4" class="character">ROSALIND</div>
	  <div id="speech5" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.8">But is all this for your father?</div>
	  </div>
	  <div class="dialog">
	  <div id="scene1.3.5">Then there were two cousins laid up; when the one</div>
	  <div id="scene1.3.6">should be lamed with reasons and the other mad</div>
	  <div id="scene1.3.7">without any.</div>
	  </div>
	  <div id="speech6" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.9">No, some of it is for my child's father. O, how</div>
	  <div id="scene1.3.10">full of briers is this working-day world!</div>
	  </div>
	  <div id="speech7" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.11">They are but burs, cousin, thrown upon thee in</div>
	  <div id="scene1.3.12">holiday foolery: if we walk not in the trodden</div>
	  <div id="scene1.3.13">paths our very petticoats will catch them.</div>
	  </div>
	  <div id="speech8" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.14">I could shake them off my coat: these burs are in my heart.</div>
	  </div>
	  <div id="speech9" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.15">Hem them away.</div>
	  </div>
	  <div id="speech10" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.16">I would try, if I could cry 'hem' and have him.</div>
	  </div>
	  <div id="speech11" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.17">Come, come, wrestle with thy affections.</div>
	  </div>
	  <div id="speech12" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.18">O, they take the part of a better wrestler than myself!</div>
	  </div>
	  <div id="speech13" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.19">O, a good wish upon you! you will try in time, in</div>
	  <div id="scene1.3.20">despite of a fall. But, turning these jests out of</div>
	  <div id="scene1.3.21">service, let us talk in good earnest: is it</div>
	  <div id="scene1.3.22">possible, on such a sudden, you should fall into so</div>
	  <div id="scene1.3.23">strong a liking with old Sir Rowland's youngest son?</div>
	  </div>
	  <div id="speech14" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.24">The duke my father loved his father dearly.</div>
	  </div>
	  <div id="speech15" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.25">Doth it therefore ensue that you should love his son</div>
	  <div id="scene1.3.26">dearly? By this kind of chase, I should hate him,</div>
	  <div id="scene1.3.27">for my father hated his father dearly; yet I hate</div>
	  <div id="scene1.3.28">not Orlando.</div>
	  </div>
	  <div id="speech16" class="character">ROSALIND</div>
	  <div title="wtf" class="dialog">
	  <div id="scene1.3.29">No, faith, hate him not, for my sake.</div>
	  </div>
	  <div id="speech17" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.30">Why should I not? doth he not deserve well?</div>
	  </div>
	  <div id="speech18" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.31">Let me love him for that, and do you love him</div>
	  <div id="scene1.3.32">because I do. Look, here comes the duke.</div>
	  </div>
	  <div id="speech19" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.33">With his eyes full of anger.</div>
	  <div class="direction">Enter DUKE FREDERICK, with Lords</div>
	  </div>
	  <div id="speech20" class="character">DUKE FREDERICK</div>
	  <div class="dialog">
	  <div id="scene1.3.34">Mistress, dispatch you with your safest haste</div>
	  <div id="scene1.3.35">And get you from our court.</div>
	  </div>
	  <div id="speech21" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.36">Me, uncle?</div>
	  </div>
	  <div id="speech22" class="character">DUKE FREDERICK</div>
	  <div class="dialog">
	  <div id="scene1.3.37">You, cousin</div>
	  <div id="scene1.3.38">Within these ten days if that thou be'st found</div>
	  <div id="scene1.3.39">So near our public court as twenty miles,</div>
	  <div id="scene1.3.40">Thou diest for it.</div>
	  </div>
	  <div id="speech23" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.41">                  I do beseech your grace,</div>
	  <div id="scene1.3.42">Let me the knowledge of my fault bear with me:</div>
	  <div id="scene1.3.43">If with myself I hold intelligence</div>
	  <div id="scene1.3.44">Or have acquaintance with mine own desires,</div>
	  <div id="scene1.3.45">If that I do not dream or be not frantic,--</div>
	  <div id="scene1.3.46">As I do trust I am not--then, dear uncle,</div>
	  <div id="scene1.3.47">Never so much as in a thought unborn</div>
	  <div id="scene1.3.48">Did I offend your highness.</div>
	  </div>
	  <div id="speech24" class="character">DUKE FREDERICK</div>
	  <div class="dialog">
	  <div id="scene1.3.49">Thus do all traitors:</div>
	  <div id="scene1.3.50">If their purgation did consist in words,</div>
	  <div id="scene1.3.51">They are as innocent as grace itself:</div>
	  <div id="scene1.3.52">Let it suffice thee that I trust thee not.</div>
	  </div>
	  <div id="speech25" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.53">Yet your mistrust cannot make me a traitor:</div>
	  <div id="scene1.3.54">Tell me whereon the likelihood depends.</div>
	  </div>
	  <div id="speech26" class="character">DUKE FREDERICK</div>
	  <div class="dialog">
	  <div id="scene1.3.55">Thou art thy father's daughter; there's enough.</div>
	  </div>
	  <div id="speech27" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.56">So was I when your highness took his dukedom;</div>
	  <div id="scene1.3.57">So was I when your highness banish'd him:</div>
	  <div id="scene1.3.58">Treason is not inherited, my lord;</div>
	  <div id="scene1.3.59">Or, if we did derive it from our friends,</div>
	  <div id="scene1.3.60">What's that to me? my father was no traitor:</div>
	  <div id="scene1.3.61">Then, good my liege, mistake me not so much</div>
	  <div id="scene1.3.62">To think my poverty is treacherous.</div>
	  </div>
	  <div id="speech28" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.63">Dear sovereign, hear me speak.</div>
	  </div>
	  <div id="speech29" class="character">DUKE FREDERICK</div>
	  <div class="dialog">
	  <div id="scene1.3.64">Ay, Celia; we stay'd her for your sake,</div>
	  <div id="scene1.3.65">Else had she with her father ranged along.</div>
	  </div>
	  <div id="speech30" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.66">I did not then entreat to have her stay;</div>
	  <div id="scene1.3.67">It was your pleasure and your own remorse:</div>
	  <div id="scene1.3.68">I was too young that time to value her;</div>
	  <div id="scene1.3.69">But now I know her: if she be a traitor,</div>
	  <div id="scene1.3.70">Why so am I; we still have slept together,</div>
	  <div id="scene1.3.71">Rose at an instant, learn'd, play'd, eat together,</div>
	  <div id="scene1.3.72">And wheresoever we went, like Juno's swans,</div>
	  <div id="scene1.3.73">Still we went coupled and inseparable.</div>
	  </div>
	  <div id="speech31" class="character">DUKE FREDERICK</div>
	  <div class="dialog">
	  <div id="scene1.3.74">She is too subtle for thee; and her smoothness,</div>
	  <div id="scene1.3.75">Her very silence and her patience</div>
	  <div id="scene1.3.76">Speak to the people, and they pity her.</div>
	  <div id="scene1.3.77">Thou art a fool: she robs thee of thy name;</div>
	  <div id="scene1.3.78">And thou wilt show more bright and seem more virtuous</div>
	  <div id="scene1.3.79">When she is gone. Then open not thy lips:</div>
	  <div id="scene1.3.80">Firm and irrevocable is my doom</div>
	  <div id="scene1.3.81">Which I have pass'd upon her; she is banish'd.</div>
	  </div>
	  <div id="speech32" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.82">Pronounce that sentence then on me, my liege:</div>
	  <div id="scene1.3.83">I cannot live out of her company.</div>
	  </div>
	  <div id="speech33" class="character">DUKE FREDERICK</div>
	  <div class="dialog">
	  <div id="scene1.3.84">You are a fool. You, niece, provide yourself:</div>
	  <div id="scene1.3.85">If you outstay the time, upon mine honour,</div>
	  <div id="scene1.3.86">And in the greatness of my word, you die.</div>
	  <div class="direction">Exeunt DUKE FREDERICK and Lords</div>
	  </div>
	  <div id="speech34" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.87">O my poor Rosalind, whither wilt thou go?</div>
	  <div id="scene1.3.88">Wilt thou change fathers? I will give thee mine.</div>
	  <div id="scene1.3.89">I charge thee, be not thou more grieved than I am.</div>
	  </div>
	  <div id="speech35" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.90">I have more cause.</div>
	  </div>
	  <div id="speech36" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.91">                  Thou hast not, cousin;</div>
	  <div id="scene1.3.92">Prithee be cheerful: know'st thou not, the duke</div>
	  <div id="scene1.3.93">Hath banish'd me, his daughter?</div>
	  </div>
	  <div id="speech37" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.94">That he hath not.</div>
	  </div>
	  <div id="speech38" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.95">No, hath not? Rosalind lacks then the love</div>
	  <div id="scene1.3.96">Which teacheth thee that thou and I am one:</div>
	  <div id="scene1.3.97">Shall we be sunder'd? shall we part, sweet girl?</div>
	  <div id="scene1.3.98">No: let my father seek another heir.</div>
	  <div id="scene1.3.99">Therefore devise with me how we may fly,</div>
	  <div id="scene1.3.100">Whither to go and what to bear with us;</div>
	  <div id="scene1.3.101">And do not seek to take your change upon you,</div>
	  <div id="scene1.3.102">To bear your griefs yourself and leave me out;</div>
	  <div id="scene1.3.103">For, by this heaven, now at our sorrows pale,</div>
	  <div id="scene1.3.104">Say what thou canst, I'll go along with thee.</div>
	  </div>
	  <div id="speech39" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.105">Why, whither shall we go?</div>
	  </div>
	  <div id="speech40" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.106">To seek my uncle in the forest of Arden.</div>
	  </div>
	  <div id="speech41" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.107">Alas, what danger will it be to us,</div>
	  <div id="scene1.3.108">Maids as we are, to travel forth so far!</div>
	  <div id="scene1.3.109">Beauty provoketh thieves sooner than gold.</div>
	  </div>
	  <div id="speech42" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.110">I'll put myself in poor and mean attire</div>
	  <div id="scene1.3.111">And with a kind of umber smirch my face;</div>
	  <div id="scene1.3.112">The like do you: so shall we pass along</div>
	  <div id="scene1.3.113">And never stir assailants.</div>
	  </div>
	  <div id="speech43" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.114">Were it not better,</div>
	  <div id="scene1.3.115">Because that I am more than common tall,</div>
	  <div id="scene1.3.116">That I did suit me all points like a man?</div>
	  <div id="scene1.3.117">A gallant curtle-axe upon my thigh,</div>
	  <div id="scene1.3.118">A boar-spear in my hand; and--in my heart</div>
	  <div id="scene1.3.119">Lie there what hidden woman's fear there will--</div>
	  <div id="scene1.3.120">We'll have a swashing and a martial outside,</div>
	  <div id="scene1.3.121">As many other mannish cowards have</div>
	  <div id="scene1.3.122">That do outface it with their semblances.</div>
	  </div>
	  <div id="speech44" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.123">What shall I call thee when thou art a man?</div>
	  </div>
	  <div id="speech45" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.124">I'll have no worse a name than Jove's own page;</div>
	  <div id="scene1.3.125">And therefore look you call me Ganymede.</div>
	  <div id="scene1.3.126">But what will you be call'd?</div>
	  </div>
	  <div id="speech46" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.127">Something that hath a reference to my state</div>
	  <div id="scene1.3.128">No longer Celia, but Aliena.</div>
	  </div>
	  <div id="speech47" class="character">ROSALIND</div>
	  <div class="dialog">
	  <div id="scene1.3.129">But, cousin, what if we assay'd to steal</div>
	  <div id="scene1.3.130">The clownish fool out of your father's court?</div>
	  <div id="scene1.3.131">Would he not be a comfort to our travel?</div>
	  </div>
	  <div id="speech48" class="character">CELIA</div>
	  <div class="dialog">
	  <div id="scene1.3.132">He'll go along o'er the wide world with me;</div>
	  <div id="scene1.3.133">Leave me alone to woo him. Let's away,</div>
	  <div id="scene1.3.134">And get our jewels and our wealth together,</div>
	  <div id="scene1.3.135">Devise the fittest time and safest way</div>
	  <div id="scene1.3.136">To hide us from pursuit that will be made</div>
	  <div id="scene1.3.137">After my flight. Now go we in content</div>
	  <div id="scene1.3.138">To liberty and not to banishment.</div>
	  <div class="direction">Exeunt</div>
	  </div>
	</div>
	</div>
</div>
</body>
</html>
'''
