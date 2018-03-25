"""Unit tests for xpyth."""

import re

import pytest

from lxml import etree
from pony.orm.decompiling import Decompiler

from xpyth import xpath, DOM, X, query


def test_iter_insertion():
    """Ensure custom node inserted as comprehension iterator."""
    assert (div for div in DOM).gi_frame.f_locals['.0'] is DOM


@pytest.mark.parametrize('comprehension,expected_expression', (
    ((div for div in DOM), '//div'),
    ((span for div in DOM for span in div), '//div//span'),
    ((span.cls for div in DOM for span in div), '//div//span/@class'),
    ((span.text for span in DOM), '//span/text()'),
    ((span for span in DOM if span.name == 'main'), "//span[@name='main']"),
    ((div for span in DOM if span.name == 'main' for div in span), "//span[@name='main']//div"),
    ((div for span in DOM for div in span if span.name == 'main'), "//span[@name='main']//div"),
    ((div for span in DOM if span.name == 'main' for div in span if div.cls == 'row'), "//span[@name='main']//div[@class='row']"),
    ((div for span in DOM for div in span if div.cls == 'row' and span.name == 'main'), "//span[@name='main']//div[@class='row']"),  # tricky case - need to dissect And
    ((a for a in DOM if a.href == 'http://www.google.com' and a.name == 'goog'), "//a[@href='http://www.google.com' and @name='goog']"),
    ((a for a in DOM if '.com' in a.href), "//a[contains(@href, '.com')]"),
    ((a for a in DOM if '.com' not in a.href), "//a[not(contains(@href, '.com'))]"),
    ((a for a in DOM if not '.com' in a.href), "//a[not(contains(@href, '.com'))]"),
    ((div for div in DOM if div.id != 'main'), "//div[@id!='main']"),
    ((div for div in DOM if not div.id == 'main'), "//div[not(@id='main')]"),
    ((X for X in DOM if X.name == 'main'), "//*[@name='main']"),
    ((span for div in DOM for X in div.following_siblings for span in X.children), '//div/following-sibling::*/span'),
    ((a.href for a in DOM if any(p for p in a.following_siblings)), '//a[./following-sibling::p]/@href'),
    ((a.href for a in DOM if any(p for p in a.following_siblings if p.id)), '//a[./following-sibling::p[@id]]/@href'),
    ((X for X in DOM if any(p for p in DOM)), '//*[//p]'),
    ((span for div in DOM for span in div if div.id in ('main', 'other')), "//div[@id='main' or @id='other']//span"),
    ((X for X in DOM if X.name in ('a', 'b', 'c')), "//*[@name='a' or @name='b' or @name='c']"),
    ((X for X in DOM if all(p for p in X if p.id == 'a')), "//*[not(.//p[not(@id='a')])]"),
    ((X for X in DOM if all(p for p in DOM if p.id == 'a')), "//*[not(//p[not(@id='a')])]"),
    ((X for X in DOM if any(p.id == 'a' for p in X)), "//*[.//p/@id='a']"),
    ((X for X in DOM if all(not p.id == 'a' for p in X)), "//*[not(.//p/@id!='a')]"),
    ((X for X in DOM if all(not p.id != 'a' for p in X)), "//*[not(.//p/@id='a')]"),
    ((X for X in DOM if len(td for td in X.following_siblings) == 0), "//*[count(./following-sibling::td)=0]"),
    ((td.text for td in DOM if td.cls == 'wideonly' and len(td for td in td.following_siblings) == 0), "//td[@class='wideonly' and count(./following-sibling::td)=0]/text()"),
    ((X for X in DOM if X.data-bind == 'a'), "//*[@data-bind='a']"),
    ((X.data-bind for X in DOM), "//*/@data-bind"),

    pytest.mark.skip(((form.action for form in DOM if all(input.name == 'a' for input in form.children)), "//form[not(./input/@name!='a')]/@action")),
    pytest.mark.skip(((X for X in DOM if all(p.id in ('a', 'b') for p in X)), "//*[not(.//p/@id='a' or .//p/@id='b')]")),
    pytest.mark.skip(((X for X in DOM if all('x' in p.id for p in X)), "//*[not(.//p[not(contains(@id, 'x'))])]")),  # Gives //*[not(.contains(@id, //p))]

    # TODO: position (e.g. xpath(a for a in (a for a in DOM)[:20]) ???)
    # TODO: position (e.g. xpath(a for X in DOM for a in X[20:]) ???)
))
def test_expression_generation(comprehension, expected_expression):
    """Ensure comprehensions are transformed into expected XPath expressions."""
    try:
        expr = xpath(comprehension)
        assert expr == expected_expression
    except AssertionError:
        ast = Decompiler(comprehension.gi_code).ast
        print(ast)
        print()
        raise


def test_context():
    """Ensure local context is handled correct when constructing expression."""
    allowed_values = 'a b c'.split()
    comprehension = (X for X in DOM if X.name in allowed_values)
    expected_expression = "//*[@name='a' or @name='b' or @name='c']"
    assert xpath(comprehension) == expected_expression


def test_lxml():
    """Ensure lxml compatibility."""
    tree = etree.fromstring('''
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
    ''')
    assert len(query(a for a in tree)) == 4
    assert query(a for a in tree if 'Not Google' in a.text)[0].attrib.get('href') != 'http://www.google.com'
    assert query(a for a in tree if 'Not Google' not in a.text)[0].attrib.get('href') == 'http://www.google.com'
    assert next(
        node 
        for node in 
        query(
            p 
            for p in 
            tree 
            if node.id
        ) 
        if re.match(r'\D+', node.attrib.get('id'))
    ).text == '123'
    assert query(  # switch between xpyth and regular comprehensions
        a 
        for a in 
        next(
            node 
            for node in 
            query(
                div 
                for div in 
                tree
            ) 
            if re.match(r'\d+', node.attrib.get('id'))
        ) 
        if 'google' in a.href
    )[0].text == 'Google Charity'
    assert set(query(
        a.href
        for a in
        tree
        if any(
            p 
            for p in 
            a.following_siblings
        )
    )) == {'http://www.google.com', 'http://www.chasestevens.com'}
    assert set(query(
        a.href
        for a in
        tree
        if not any(
            p 
            for p in 
            a.following_siblings
        )
    )) == {'http://www.google.org', 'http://www.chasestevens.org'}
    assert set(query(
        a.href
        for a in
        tree
        if not any(
            p 
            for p in 
            a.following_siblings
        )
        and any(
            p 
            for p in 
            a.following_siblings
        )
    )) == set()
    assert set(query(
        a.href 
        for a in 
        tree 
        if any(
            p 
            for p in 
            tree
        )
    )) == {'http://www.google.com', 'http://www.chasestevens.com', 'http://www.google.org', 'http://www.chasestevens.org'}
    assert not query(
        a.href 
        for a in 
        tree 
        if not any(
            p 
            for p in 
            tree
        )
    )
