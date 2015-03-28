# xpyth
A module for querying the DOM tree and writing XPath expressions using Python generators.

Example usage::
```python
>>> from xpyth import expression, DOM
>>> expression(span for div in DOM if div.id == 'main' for span in div)
"//div[@id='main']//span"
>>> expression(a for a in DOM if '.com' not in a.href)
"//a[not(contains(@href, '.com'))]"
```
