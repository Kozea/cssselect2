from urllib import urlopen
from urlparse import urljoin
import timeit

import html5lib
import tinycss2
import cssselect2


def parse(url):
    root = html5lib.parse(urlopen(url))
    matcher = cssselect2.Matcher()
    for element in root.iter():
        if element.tag == '{http://www.w3.org/1999/xhtml}style':
            rules = tinycss2.parse_stylesheet(element.text)
        elif (element.tag == '{http://www.w3.org/1999/xhtml}link' and
              element.get('rel').strip() == 'stylesheet'):
            rules, _ = tinycss2.parse_stylesheet_bytes(
                urlopen(urljoin(url, element.get('href'))).read())
        else:
            continue

        for rule in rules:
            # Ignore all at-rules
            if rule.type == 'qualified-rule':
                try:
                    selectors = cssselect2.compile_selector_list(rule.prelude)
                except cssselect2.SelectorError as error:
                    print('Invalid selector: %s %s'
                          % (tinycss2.serialize(rule.prelude), error))
                else:
                    for selector in selectors:
                        matcher.add_selector(selector, None)
    return root, matcher


def match(root, matcher):
    for element in cssselect2.ElementWrapper.from_root(root).iter_subtree():
        for _ in matcher.match(element):
            pass


if __name__ == '__main__':
    root, matcher = parse('http://dev.w3.org/csswg/selectors4/')
    for t in timeit.repeat(lambda: match(root, matcher), number=3):
        print('%.3f' % t)
