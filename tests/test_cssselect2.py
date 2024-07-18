"""

Test suite for cssselect2.

"""

import xml.etree.ElementTree as etree  # noqa: N813
from pathlib import Path

import pytest

from cssselect2 import ElementWrapper, SelectorError, compile_selector_list

from .w3_selectors import invalid_selectors, valid_selectors

CURRENT_FOLDER = Path(__file__).parent
IDS_ROOT = etree.parse(CURRENT_FOLDER / 'ids.html')
ALL_IDS = [
    element.etree_element.get('id', 'nil') for element in
    ElementWrapper.from_html_root(IDS_ROOT).query_all('*')]
SHAKESPEARE_BODY = (
    ElementWrapper.from_xml_root(
        etree.parse(CURRENT_FOLDER / 'shakespeare.html').find(
            './/{http://www.w3.org/1999/xhtml}body')))


def get_test_document():
    document = etree.parse(CURRENT_FOLDER / 'content.xhtml')
    parent = document.find(".//*[@id='root']")

    # Setup namespace tests
    for id in ('any-namespace', 'no-namespace'):
        div = etree.SubElement(parent, '{http://www.w3.org/1999/xhtml}div')
        div.set('id', id)
        div1 = etree.SubElement(div, '{http://www.w3.org/1999/xhtml}div')
        div1.set('id', id + '-div1')
        div2 = etree.SubElement(div, '{http://www.w3.org/1999/xhtml}div')
        div2.set('id', id + '-div2')
        div3 = etree.SubElement(div, 'div')
        div3.set('id', id + '-div3')
        div4 = etree.SubElement(div, '{http://www.example.org/ns}div')
        div4.set('id', id + '-div4')

    return document


TEST_DOCUMENT = get_test_document()


# Remove unsuitable tests
valid_selectors = [
    test for test in valid_selectors
    if not set(test.get('exclude', ())) & {'document', 'xhtml'}]

# Mark failing tests
for failing in (2, 9, 104, 105, 111, 197, 198):
    valid_selectors[failing] = pytest.param(
        valid_selectors[failing], marks=pytest.mark.xfail)


@pytest.mark.parametrize('test', invalid_selectors)
def test_invalid_selectors(test):
    try:
        compile_selector_list(test['selector'])
    except SelectorError:
        pass
    else:  # pragma: no cover
        raise AssertionError(
            f'Should be invalid: {test["selector"]!r} ({test["name"]})')


@pytest.mark.parametrize('test', valid_selectors)
def test_valid_selectors(test):
    root = ElementWrapper.from_xml_root(TEST_DOCUMENT)
    result = [element.id for element in root.query_all(test['selector'])]
    if result != test['expect']:  # pragma: no cover
        raise AssertionError(
            f'{test["selector"]!r}: {result} != {test["expect"]} ({test["name"]})')


def test_lang():
    doc = etree.fromstring('''
        <html xmlns="http://www.w3.org/1999/xhtml"></html>
    ''')
    assert not ElementWrapper.from_xml_root(doc).matches(':lang(fr)')

    doc = etree.fromstring('''
        <html xmlns="http://www.w3.org/1999/xhtml">
            <meta http-equiv="Content-Language" content=" fr \t"/>
        </html>
    ''')
    root = ElementWrapper.from_xml_root(doc, content_language='en')
    assert root.matches(':lang(fr)')

    doc = etree.fromstring('''
        <html>
            <meta http-equiv="Content-Language" content=" fr \t"/>
        </html>
    ''')
    root = ElementWrapper.from_xml_root(doc, content_language='en')
    assert root.matches(':lang(en)')

    doc = etree.fromstring('<html></html>')
    root = ElementWrapper.from_xml_root(doc, content_language='en')
    assert root.matches(':lang(en)')

    root = ElementWrapper.from_xml_root(doc, content_language='en, es')
    assert not root.matches(':lang(en)')

    root = ElementWrapper.from_xml_root(doc)
    assert not root.matches(':lang(en)')

    doc = etree.fromstring('<html lang="eN"></html>')
    root = ElementWrapper.from_html_root(doc)
    assert root.matches(':lang(en)')

    doc = etree.fromstring('<html lang="eN"></html>')
    root = ElementWrapper.from_xml_root(doc)
    assert not root.matches(':lang(en)')


@pytest.mark.parametrize('selector, result', (
    ('*', ALL_IDS),
    ('div', ['outer-div', 'li-div', 'foobar-div']),
    ('div div', ['li-div']),
    ('div, div div', ['outer-div', 'li-div', 'foobar-div']),
    ('div , div div', ['outer-div', 'li-div', 'foobar-div']),
    ('a[name]', ['name-anchor']),
    ('a[rel]', ['tag-anchor', 'nofollow-anchor']),
    ('a[rel="tag"]', ['tag-anchor']),
    ('a[href*="localhost"]', ['tag-anchor']),
    ('a[href*=""]', []),
    ('a[href^="http"]', ['tag-anchor', 'nofollow-anchor']),
    ('a[href^="http:"]', ['tag-anchor']),
    ('a[href^=""]', []),
    ('a[href$="org"]', ['nofollow-anchor']),
    ('a[href$=""]', []),
    ('div[foobar~="bc"]', ['foobar-div']),
    ('div[foobar~="cde"]', ['foobar-div']),
    ('[foobar~="ab bc"]', []),
    ('[foobar~=""]', []),
    ('[foobar~=" \t"]', []),
    ('div[foobar~="cd"]', []),

    ('a[rel="tAg"]', []),
    ('a[rel="tAg" s]', []),
    ('a[rel="tAg" i]', ['tag-anchor']),
    ('a[href*="localHOST"]', []),
    ('a[href*="localHOST" s]', []),
    ('a[href*="localHOST" i]', ['tag-anchor']),
    ('a[href^="hTtp"]', []),
    ('a[href^="hTtp" s]', []),
    ('a[href^="hTtp" i]', ['tag-anchor', 'nofollow-anchor']),
    ('a[href$="Org"]', []),
    ('a[href$="Org" S]', []),
    ('a[href$="Org" I]', ['nofollow-anchor']),
    ('div[foobar~="BC"]', []),
    ('div[foobar~="BC" s]', []),
    ('div[foobar~="BC" i]', ['foobar-div']),

    # Attribute values are case sensitive…
    ('*[lang|="En"]', ['second-li']),
    ('[lang|="En-us"]', ['second-li']),
    ('*[lang|="en"]', []),
    ('[lang|="en-US"]', []),
    ('*[lang|="e"]', []),
    # … but :lang() is not.
    (':lang(EN)', ['second-li', 'li-div']),
    ('*:lang(en-US)', ['second-li', 'li-div']),
    (':lang(En)', ['second-li', 'li-div']),
    (':lang(e)', []),
    (':lang("en-US")', ['second-li', 'li-div']),
    pytest.param(
        ':lang("*-US")', ['second-li', 'li-div'], marks=pytest.mark.xfail),
    pytest.param(
        ':lang(\\*-US)', ['second-li', 'li-div'], marks=pytest.mark.xfail),
    (':lang(en /* English */, fr /* French */)', ['second-li', 'li-div']),

    ('li:nth-child(3)', ['third-li']),
    ('li:nth-child(10)', []),
    ('li:nth-child(2n)', ['second-li', 'fourth-li', 'sixth-li']),
    ('li:nth-child(even)', ['second-li', 'fourth-li', 'sixth-li']),
    ('li:nth-child(+2n+0)', ['second-li', 'fourth-li', 'sixth-li']),
    ('li:nth-child(2n+1)', ['first-li', 'third-li', 'fifth-li', 'seventh-li']),
    ('li:nth-child(odd)', ['first-li', 'third-li', 'fifth-li', 'seventh-li']),
    ('li:nth-child(2n+4)', ['fourth-li', 'sixth-li']),
    ('li:nth-child(3n+1)', ['first-li', 'fourth-li', 'seventh-li']),
    ('p > input:nth-child(2n of p input[type=checkbox])', [
        'checkbox-disabled', 'checkbox-disabled-checked']),
    ('li:nth-last-child(1)', ['seventh-li']),
    ('li:nth-last-child(0)', []),
    ('li:nth-last-child(2n+2)', ['second-li', 'fourth-li', 'sixth-li']),
    ('li:nth-last-child(even)', ['second-li', 'fourth-li', 'sixth-li']),
    ('li:nth-last-child(2n+4)', ['second-li', 'fourth-li']),
    (':nth-last-child(1 of [type=checkbox])', [
        'checkbox-disabled-checked', 'checkbox-fieldset-disabled']),
    ('ol:first-of-type', ['first-ol']),
    ('ol:nth-child(1)', []),
    ('ol:nth-of-type(2)', ['second-ol']),
    (':nth-of-type(1 of .e)', ['tag-anchor', 'first-ol']),
    ('ol:nth-last-of-type(2)', ['first-ol']),
    (':nth-last-of-type(1 of .e)', ['tag-anchor', 'second-ol']),
    ('span:only-child', ['foobar-span']),
    ('div:only-child', ['li-div']),
    ('div *:only-child', ['li-div', 'foobar-span']),
    ('p *:only-of-type', ['p-em', 'fieldset']),
    ('p:only-of-type', ['paragraph']),

    ('a:empty', ['name-anchor']),
    ('a:EMpty', ['name-anchor']),
    ('li:empty', ['third-li', 'fourth-li', 'fifth-li', 'sixth-li']),
    (':root', ['html']),
    ('html:root', ['html']),
    ('li:root', []),
    ('* :root', []),
    ('.a', ['first-ol']),
    ('.b', ['first-ol']),
    ('*.a', ['first-ol']),
    ('ol.a', ['first-ol']),
    ('.c', ['first-ol', 'third-li', 'fourth-li']),
    ('*.c', ['first-ol', 'third-li', 'fourth-li']),
    ('ol *.c', ['third-li', 'fourth-li']),
    ('ol li.c', ['third-li', 'fourth-li']),
    ('li ~ li.c', ['third-li', 'fourth-li']),
    ('ol > li.c', ['third-li', 'fourth-li']),
    ('#first-li', ['first-li']),
    ('li#first-li', ['first-li']),
    ('*#first-li', ['first-li']),
    ('li div', ['li-div']),
    ('li > div', ['li-div']),
    ('div div', ['li-div']),
    ('div > div', []),
    ('div>.c', ['first-ol']),
    ('div > .c', ['first-ol']),
    ('div + div', ['foobar-div']),
    ('a ~ a', ['tag-anchor', 'nofollow-anchor']),
    ('a[rel="tag"] ~ a', ['nofollow-anchor']),
    ('ol#first-ol li:last-child', ['seventh-li']),
    ('ol#first-ol *:last-child', ['li-div', 'seventh-li']),
    ('#outer-div:first-child', ['outer-div']),
    ('#outer-div :first-child', [
        'name-anchor', 'first-li', 'li-div', 'p-b',
        'checkbox-fieldset-disabled', 'area-href']),
    ('a[href]', ['tag-anchor', 'nofollow-anchor']),
    (':not(*)', []),
    ('a:not([href])', ['name-anchor']),
    ('ol :Not([class])', [
        'first-li', 'second-li', 'li-div',
        'fifth-li', 'sixth-li', 'seventh-li']),
    ('li:not(:nth-child(odd), #second-li)', ['fourth-li', 'sixth-li']),
    ('li:not(li)', []),
    (':is(*)', ALL_IDS),
    (':is(div)', ['outer-div', 'li-div', 'foobar-div']),
    (':is(div, fieldset)', ['outer-div', 'li-div', 'fieldset', 'foobar-div']),
    (':is(:::wrong)', []),
    (':is(div, :::wrong, fieldset)', [
        'outer-div', 'li-div', 'fieldset', 'foobar-div']),
    ('div :is(div, div)', ['li-div']),
    ('li:is(.c)', ['third-li', 'fourth-li']),
    ('input:is([type="text"])', ['text-checked']),
    ('div:is(:not(#outer-div))', ['li-div', 'foobar-div']),
    ('div:is(div::before)', []),
    (':where(*)', ALL_IDS),
    (':where(div)', ['outer-div', 'li-div', 'foobar-div']),
    (':where(div, fieldset)', [
        'outer-div', 'li-div', 'fieldset', 'foobar-div']),
    (':where(:::wrong)', []),
    (':where(div, :::wrong, fieldset)', [
        'outer-div', 'li-div', 'fieldset', 'foobar-div']),
    ('div :where(div, div)', ['li-div']),
    ('li:where(.c)', ['third-li', 'fourth-li']),
    ('input:where([type="text"])', ['text-checked']),
    ('div:where(:not(#outer-div))', ['li-div', 'foobar-div']),
    ('div:where(div::before)', []),
    ('p:has(input)', ['paragraph']),
    ('p:has(fieldset input)', ['paragraph']),
    ('p:has(> fieldset)', ['paragraph']),
    ('ol:has(> div)', []),
    ('ol:has(input, li)', ['first-ol']),
    ('ol:has(input, fieldset)', []),
    ('ol:has(+ p)', ['first-ol']),
    ('ol:has(~ ol)', ['first-ol']),
    ('ol:has(>a, ~ ol)', ['first-ol']),
    ('ol:has(a,ol,  li  )', ['first-ol']),
    ('ol:has(*)', ['first-ol']),
    ('ol:has(:not(li))', ['first-ol']),
    ('ol:has( > :not( li ))', []),
    ('ol:has(:not(li, div))', []),

    # Invalid characters in XPath element names, should not crash
    (r'di\a0 v', []),
    (r'div\[', []),
    (r'[h\a0 ref]', []),
    (r'[h\]ref]', []),

    (':link', ['link-href', 'tag-anchor', 'nofollow-anchor', 'area-href']),
    (':any-link', ['link-href', 'tag-anchor', 'nofollow-anchor', 'area-href']),
    (':local-link', ['link-href', 'area-href']),
    (':visited', []),
    (':hover', []),
    (':active', []),
    (':focus', []),
    (':target', []),
    (':enabled', [
        'link-href', 'tag-anchor', 'nofollow-anchor', 'checkbox-unchecked',
        'text-checked', 'input-hidden', 'checkbox-checked', 'area-href']),
    (':disabled', [
        'checkbox-disabled', 'input-hidden-disabled',
        'checkbox-disabled-checked', 'fieldset', 'checkbox-fieldset-disabled',
        'hidden-fieldset-disabled']),
    (':checked', ['checkbox-checked', 'checkbox-disabled-checked']),

    ('a:not([href]), div div', ['name-anchor', 'li-div']),
    ('a:not([href]) /* test */, div div', ['name-anchor', 'li-div']),
    ('a:not([href]), /* test */ div div', ['name-anchor', 'li-div']),
    ('/* test */a:not([href]),div div', ['name-anchor', 'li-div']),
    ('a:not([href]) , div div/* test */', ['name-anchor', 'li-div']),
    ('/* test */a:not([href]), /* test */ div div', ['name-anchor', 'li-div']),
    ('/* test */a:not([href])/* test */,div  div', ['name-anchor', 'li-div']),
    ('/* test */ a:not([href]), div/* test */ div', ['name-anchor', 'li-div']),
    ('a:not([href]) /* test */,/* test */div  div', ['name-anchor', 'li-div']),
))
def test_select(selector, result):
    xml_ids = [
        element.etree_element.get('id', 'nil') for element in
        ElementWrapper.from_xml_root(IDS_ROOT).query_all(selector)]
    html_ids = [
        element.etree_element.get('id', 'nil') for element in
        ElementWrapper.from_html_root(IDS_ROOT).query_all(selector)]
    assert xml_ids == html_ids == result


@pytest.mark.parametrize('selector, result', (
    ('DIV', ['outer-div', 'li-div', 'foobar-div']),
    ('a[NAme]', ['name-anchor']),
    ('HTML :link', [
        'link-href', 'tag-anchor', 'nofollow-anchor', 'area-href']),
))
def test_html_select(selector, result):
    assert not [
        element.etree_element.get('id', 'nil') for element in
        ElementWrapper.from_xml_root(IDS_ROOT).query_all(selector)]
    assert result == [
        element.etree_element.get('id', 'nil') for element in
        ElementWrapper.from_html_root(IDS_ROOT).query_all(selector)]


# Data borrowed from http://mootools.net/slickspeed/
@pytest.mark.parametrize('selector, result', (
    # Changed from original because we’re only searching the body.
    # ('*', 252),
    ('*', 246),
    # ('div:contains(CELIA)', 26),
    ('div:only-child', 22),  # ?
    ('div:nth-child(even)', 106),
    ('div:nth-child(2n)', 106),
    ('div:nth-child(odd)', 137),
    ('div:nth-child(2n+1)', 137),
    ('div:nth-child(n)', 243),
    ('div:last-child', 53),
    ('div:first-child', 51),
    ('div > div', 242),
    ('div + div', 190),
    ('div ~ div', 190),
    ('body', 1),
    ('body div', 243),
    ('div', 243),
    ('div div', 242),
    ('div div div', 241),
    ('div, div, div', 243),
    ('div, a, span', 243),
    ('.dialog', 51),
    ('div.dialog', 51),
    ('div .dialog', 51),
    ('div.character, div.dialog', 99),
    ('div.direction.dialog', 0),
    ('div.dialog.direction', 0),
    ('div.dialog.scene', 1),
    ('div.scene.scene', 1),
    ('div.scene .scene', 0),
    ('div.direction .dialog ', 0),
    ('div .dialog .direction', 4),
    ('div.dialog .dialog .direction', 4),
    ('#speech5', 1),
    ('div#speech5', 1),
    ('div #speech5', 1),
    ('div.scene div.dialog', 49),
    ('div#scene1 div.dialog div', 142),
    ('#scene1 #speech1', 1),
    ('div[class]', 103),
    ('div[class=dialog]', 50),
    ('div[class^=dia]', 51),
    ('div[class$=log]', 50),
    ('div[class*=sce]', 1),
    ('div[class|=dialog]', 50),  # ? Seems right
    # assert count('div[class!=madeup]', 243),  # ? Seems right
    ('div[class~=dialog]', 51),  # ? Seems right
))
def test_select_shakespeare(selector, result):
    assert sum(1 for _ in SHAKESPEARE_BODY.query_all(selector)) == result
