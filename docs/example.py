from xml.etree import ElementTree

import cssselect2
import tinycss2

# Parse CSS and add rules to the matcher

matcher = cssselect2.Matcher()

rules = tinycss2.parse_stylesheet('''
  body { font-size: 2em }
  body p { background: red }
  p { color: blue }
''', skip_whitespace=True)

for rule in rules:
    selectors = cssselect2.compile_selector_list(rule.prelude)
    selector_string = tinycss2.serialize(rule.prelude)
    content_string = tinycss2.serialize(rule.content)
    payload = (selector_string, content_string)
    for selector in selectors:
        matcher.add_selector(selector, payload)


# Parse HTML and find CSS rules applying to each tag

html_tree = ElementTree.fromstring('''
  <html>
    <body>
      <p>Test</p>
    </body>
  </html>
''')
wrapper = cssselect2.ElementWrapper.from_html_root(html_tree)
for element in wrapper.iter_subtree():
    tag = element.etree_element.tag.split('}')[-1]
    print('Found tag "{}" in HTML'.format(tag))

    matches = matcher.match(element)
    if matches:
        for match in matches:
            specificity, order, pseudo, payload = match
            selector_string, content_string = payload
            print('Matching selector "{}" ({})'.format(
                selector_string, content_string))
    else:
        print('No rule matching this tag')
    print()
