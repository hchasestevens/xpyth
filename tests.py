from xpyth import xpath, DOM, X, query
from lxml import etree
from pony.orm.decompiling import Decompiler


def tests():
    def assert_eq(x, y):
        try:
            expr = xpath(x)
            assert expr == y, expr
        except AssertionError:
            ast = Decompiler(x.gi_code).ast
            print ast
            print
            raise
    
    assert (div for div in DOM).gi_frame.f_locals['.0'] == DOM

    assert_eq((div for div in DOM), '//div')
    assert_eq((span for div in DOM for span in div), '//div//span')
    assert_eq((span.cls for div in DOM for span in div), '//div//span/@class')
    assert_eq((span.text for span in DOM), '//span/text()')
    assert_eq((span for span in DOM if span.name == 'main'), "//span[@name='main']")
    assert_eq((div for span in DOM if span.name == 'main' for div in span), "//span[@name='main']//div")
    assert_eq((div for span in DOM for div in span if span.name == 'main'), "//span[@name='main']//div")
    assert_eq((div for span in DOM if span.name == 'main' for div in span if div.cls == 'row'), "//span[@name='main']//div[@class='row']")
    assert_eq((div for span in DOM for div in span if div.cls == 'row' and span.name == 'main'), "//span[@name='main']//div[@class='row']")  # tricky case - need to dissect And
    assert_eq((a for a in DOM if a.href == 'http://www.google.com' and a.name == 'goog'), "//a[@href='http://www.google.com' and @name='goog']")
    assert_eq((a for a in DOM if '.com' in a.href), "//a[contains(@href, '.com')]")
    assert_eq((a for a in DOM if '.com' not in a.href), "//a[not(contains(@href, '.com'))]")
    assert_eq((a for a in DOM if not '.com' in a.href), "//a[not(contains(@href, '.com'))]")
    assert_eq((div for div in DOM if div.id != 'main'), "//div[@id!='main']")
    assert_eq((div for div in DOM if not div.id == 'main'), "//div[not(@id='main')]")
    assert_eq((X for X in DOM if X.name == 'main'), "//*[@name='main']")
    assert_eq((span for div in DOM for X in div.following_siblings for span in X.children), '//div/following-sibling::*/span')
    assert_eq((a.href for a in DOM if any(p for p in a.following_siblings)), '//a[./following-sibling::p]/@href')
    assert_eq((a.href for a in DOM if any(p for p in a.following_siblings if p.id)), '//a[./following-sibling::p[@id]]/@href')
    assert_eq((X for X in DOM if any(p for p in DOM)), '//*[//p]')
    assert_eq((span for div in DOM for span in div if div.id in ('main', 'other')), "//div[@id='main' or @id='other']//span")
    assert_eq((X for X in DOM if X.name in ('a', 'b', 'c')), "//*[@name='a' or @name='b' or @name='c']")
    allowed_values = 'a b c'.split()
    assert_eq((X for X in DOM if X.name in allowed_values), "//*[@name='a' or @name='b' or @name='c']")
    allowed_values = map(str, range(5))
    assert_eq((X for X in DOM if X.value in allowed_values), "//*[@value='0' or @value='1' or @value='2' or @value='3' or @value='4']")
    assert_eq((X for X in DOM if all(p for p in X if p.id == 'a')), "//*[not(.//p[not(@id='a')])]")
    assert_eq((X for X in DOM if all(p for p in DOM if p.id == 'a')), "//*[not(//p[not(@id='a')])]")
    assert_eq((X for X in DOM if any(p.id == 'a' for p in X)), "//*[.//p/@id='a']")
    assert_eq((X for X in DOM if all(not p.id == 'a' for p in X)), "//*[not(.//p/@id!='a')]")
    assert_eq((X for X in DOM if all(not p.id != 'a' for p in X)), "//*[not(.//p/@id='a')]")
    assert_eq((X for X in DOM if len(td for td in X.following_siblings) == 0), "//*[count(./following-sibling::td)=0]")
    assert_eq((td.text for td in DOM if td.cls == 'wideonly' and len(td for td in td.following_siblings) == 0), "//td[@class='wideonly' and count(./following-sibling::td)=0]/text()")
    assert_eq((X for X in DOM if X.data-bind == 'a'), "//*[@data-bind='a']")
    assert_eq((X.data-bind for X in DOM), "//*/@data-bind")
    #assert_eq((form.action for form in DOM if all(input.name == 'a' for input in form.children)), "//form[not(./input/@name!='a')]/@action")
    #assert_eq((X for X in DOM if all(p.id in ('a', 'b') for p in X)), "//*[not(.//p/@id='a' or .//p/@id='b')]")
    #assert_eq((X for X in DOM if all('x' in p.id for p in X)), "//*[not(.//p[not(contains(@id, 'x'))])]")  # Gives //*[not(.contains(@id, //p))]
    #TODO: position (e.g. xpath(a for a in (a for a in DOM)[:20]) ???)
    #TODO: position (e.g. xpath(a for X in DOM for a in X[20:]) ???)

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
    import re
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


if __name__ == '__main__':
    tests()