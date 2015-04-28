# xpyth
A module for querying the DOM tree and writing XPath expressions using Python generators.

Example usage:
```python
>>> from xpyth import xpath, DOM, X

>>> xpath(X for X in DOM if X.name == 'main')
"//*[@name='main']"

>>> xpath(span for div in DOM for span in div if div.id == 'main')
"//div[@id='main']//span"

>>> xpath(a for a in DOM if '.com' not in a.href)
"//a[not(contains(@href, '.com'))]"

>>> xpath(a.href for a in DOM if any(p for p in a.ancestors if p.id))
"//a[./ancestor::p[@id]]/@href"

>>> xpath(form.action for form in DOM if all(input for input in form.children if input.value == 'a'))
"//form[not(./input[not(@value='a')])]/@action"

>>> allowed_ids = list('abc')
>>> xpath(X for X in DOM if x.id in allowed_ids)
"//*[@id='a' or @id='b' or @id='c']"
```
