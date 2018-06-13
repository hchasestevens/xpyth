# xpyth

[![Build Status](https://travis-ci.org/hchasestevens/xpyth.svg?branch=master)](https://travis-ci.org/hchasestevens/xpyth)
[![PyPI version](https://badge.fury.io/py/xpyth.svg)](https://badge.fury.io/py/xpyth)
![PyPI - Python Version](https://img.shields.io/pypi/pyversions/xpyth.svg) 

A module for querying the DOM tree and writing XPath expressions using native Python syntax.

Example usage
-------------
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

>>> xpath(X.data-bind for X in DOM if X.data-bind == '1')
"//*[@data-bind='1']/@data-bind"

>>> xpath(
...     form.action 
...     for form in DOM 
...     if all(
...         input 
...         for input in form.children 
...         if input.value == 'a'
...     )
... )
"//form[not(./input[not(@value='a')])]/@action"

>>> allowed_ids = list('abc')
>>> xpath(X for X in DOM if X.id in allowed_ids)
"//*[@id='a' or @id='b' or @id='c']"
```

Motivation
----------

XPath is the de facto standard in querying XML and HTML documents. In Python (and most other languages), XPath expressions are represented as strings; this not only constitutes a potential security threat, but also means that developers are denied standard text-editor and IDE features such as syntax highlighting and autocomplete when writing XPaths. Furthermore, having to become familiar with XPath (or CSS selectors) presents a barrier to entry for developers who want to interact with the web.

[Great inroads](https://msdn.microsoft.com/en-us/library/bb397933.aspx) have been made in various programming languages in allowing the use of native list-comprehension-like syntax to generate SQL queries. __xpyth__ piggybacks off one such effort, [Pony](http://ponyorm.com/), to extend this functionality to XPath. __Now anyone familiar with Python comprehension syntax can query XML/HTML documents quickly and easily__. Moreover, __xpyth__ integrates with the popular [lxml](http://lxml.de/) library to enable developers to go beyond the querying capabilities of XPath (when necessary).

Installation
------------

```bash
pip install xpyth
```


Use with lxml
-------------

__xpyth__ supports querying lxml ```ElementTree```s using the ```query``` function. For example, given a document
```html
<html>
    <div id='main' class='main'>
        <a href='http://www.google.com'>Google</a>
        <a href='http://www.chasestevens.com'>Not Google</a>
        <p>Lorem ipsum</p>
        <p id='123'>no numbers here</p>
        <p id='numbers_only'>123</p>
    </div>
    <div id='123' class='secondary'>
        <a href='http://www.google.org'>Google Charity</a>
        <a href='http://www.chasestevens.org'>Broken link!</a>
    </div>
</html>
```
accessible as the ```ElementTree``` ```tree```, the following can be executed:
```python
>>> len(query(a for a in tree))
4
>>> query(a for a in tree if 'Not Google' not in a.text)[0].attrib.get('href')
"http://www.google.com"
>>> next(
...     node 
...     for node in 
...     query(
...         p 
...         for p in 
...         tree 
...         if p.id
...     ) 
...     if re.match(r'\D+', node.attrib.get('id'))
... ).text
"123"
```

Known Issues
------------

*  HTML tag names that contain special characters (dashes) cannot be selected, as they violate Python's generator comprehension syntax. HTML attributes containing dashes, e.g. ``data-bind``, work normally.
*  The use of ```all``` is quite buggy, e.g. the following return incorrect expressions:

   ```python
   >>> xpath(X for X in DOM if all(p.id in ('a', 'b') for p in X))
   "//*[not(.//p/@id='a' or //p/@id='b')]"  # expected "//*[not(.//p[./@id!='a' and ./@id!='b'])]"
   >>> xpath(X for X in DOM if all('x' in p.id for p in X))
   "//*[not(.contains(@id, //p))]"  # expected "//*[not(.//p[not(contains(@id, 'x'))])]"
   ```
    
Contacts
--------

* Name: [H. Chase Stevens](http://www.chasestevens.com)
* Twitter: [@hchasestevens](https://twitter.com/hchasestevens)
