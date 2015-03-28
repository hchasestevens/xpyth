from pony.orm.decompiling import Decompiler
from pony.thirdparty.compiler.ast import *
from lxml import etree

import ctypes


class _DOM(object):
    def __iter__(self):
        return self
    def next(self):
        return self

DOM = _DOM()


class X:
    '''Wildcard, to give autocomplete suggestions.'''
    (text,
     ancestors,
     ancestors_or_self,
     children,
     descendants,
     descendants_or_self,
     following,
     followings,
     following_siblings,
     parent,
     parents,
     preceding,
     precedings,
     preceding_siblings,
     self) = [None] * 15


def xpath(g):
    """Returns XPath expression corresponding to generator."""
    assert g.gi_frame.f_locals['.0'] == DOM, "Only root-level expressions are supported."
    ast = Decompiler(g.gi_code).ast
    frame_locals = g.gi_frame.f_locals
    return _xpathify(ast, frame_locals)


def query(g):
    """Queries a DOM tree (lxml Element)."""
    try:
        dom = next(g.gi_frame.f_locals['.0']).getparent()
    except StopIteration:
        return []  # copying what lxml does
    
    # Magic to convert our generator into a DOM-generator (http://pydev.blogspot.co.uk/2014/02/changing-locals-of-frame-frameflocals.html)
    g.gi_frame.f_locals['.0'] = DOM
    ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(g.gi_frame), ctypes.c_int(0))
    
    expression = '.' + xpath(g)
    return dom.xpath(expression)


_ATTR_REPLACEMENTS = {
    'cls': 'class',
    '__class__': 'class',
}

_ATTR_FORMAT_OVERRIDES = {
    'text': '{}()',
}

_COMPARE_OP_REPLACEMENTS = {
    '==': '=',
    'in': 'contains',
}

_COMPARE_OP_FORMAT_OVERRIDES = {
    'contains': '{1}({2}, {0})',
    'not in': 'not(contains({2}, {0}))',
}

_GENEXPRFOR_GETATTR_SEP_OVERRIDES = {
    'ancestors': '/ancestor::',
    'ancestors_or_self': '/ancestor-or-self::',
    'children': '/',
    'descendants': '/descendant::',
    'descendants_or_self': '/descendant-or-self::',
    'following': '/following::',
    'followings': '/following::',
    'following_siblings': '/following-sibling::',
    'parent': '/parent::',
    'parents': '/parent::',
    'preceding': '/preceding::',
    'precedings': '/preceding::',
    'preceding_siblings': '/preceding-sibling::',
    'self': '/self::',
}


def _root_level(genexpr, frame_locals):
    genexprfor_src = genexpr.code.quals[0].getChildren()[1]
    if genexprfor_src.__class__ == Name:
        name = genexprfor_src.name
        known_dom = name in ('DOM', '.0')
        return known_dom or isinstance(frame_locals.get(name), etree._Element)


def _get_highest_src(if_, ranked_srcs):
    ntype = if_.__class__
    
    if ntype == GenExprIf:
        return _get_highest_src(if_.test, ranked_srcs)
    
    if ntype in (Name, AssName):
        return [if_.name]

    if hasattr(if_, 'getChildren'):
        srcs = [
            src
            for child in 
            if_.getChildren()
            for src in 
            _get_highest_src(child, ranked_srcs)
            if src in ranked_srcs
        ]
        if srcs:
            return [sorted(srcs, key=ranked_srcs.index)[0]]

    return []


def _xpathify(ast_subtree, frame_locals):
    """Returns a string for a subtree of the AST."""
    ntype = ast_subtree.__class__
    children = ast_subtree.getChildren()

    if ntype == GenExpr:
        child, = children
        return _xpathify(child, frame_locals)

    elif ntype == GenExprInner:
        name = children[0]
        fors = children[1:]

        # Rearrange ifs
        for_srcs = {for_.assign.name: for_ for for_ in fors if for_.__class__}
        ranked_srcs = (for_.getChildren()[1] for for_ in fors)
        ranked_src_names = [
            src.getChildren()[0].name 
            if src.__class__ == Getattr 
            else src.name 
            for src in 
            ranked_srcs
        ]
        for for_ in fors:
            for_src = for_.assign.name
            ifs = for_.ifs[:]
            for if_ in ifs:
                highest_src = _get_highest_src(if_, ranked_src_names)
                if not highest_src:
                    continue
                highest_src, = highest_src
                if highest_src != for_src:
                    for_srcs[highest_src].ifs.append(if_)
                    for_.ifs.remove(if_)

        fors = ''.join([_xpathify(for_, frame_locals) for for_ in fors])
        if isinstance(name, Getattr):
            return '{}/{}'.format(fors, _xpathify(name, frame_locals))
        return fors

    elif ntype in (Name, AssName):
        name = ast_subtree.name
        if name == '.0':
            return '.'
        if name == 'X':
            return '*'
        return name

    elif ntype == GenExprFor:
        name, src = children[:2]
        conds = children[2:]
        sep = '//'
        if isinstance(src, Getattr):
            sep = _GENEXPRFOR_GETATTR_SEP_OVERRIDES.get(src.attrname, '//')
        if not conds:
            return '{}{}'.format(sep, _xpathify(name, frame_locals))  # slashes are contingent on src
        return '{}{}[{}]'.format(sep, _xpathify(name, frame_locals), _xpathify(conds[0], frame_locals))  # 0?

    elif ntype == Getattr:
        name, attr = children
        attr = _ATTR_REPLACEMENTS.get(attr, attr)
        # this might need to be context-sensitive... Almost assuredly, actually
        # consider: .//div/@class, .//div[./@class='x']
        return _ATTR_FORMAT_OVERRIDES.get(attr, '@{}').format(attr)

    elif ntype == GenExprIf:
        if len(children) == 1:
            return _xpathify(children[0], frame_locals)
        raise NotImplementedError, children

    elif ntype == Compare:
        if len(children) == 3:
            n1, op, n2 = children
            op = _COMPARE_OP_REPLACEMENTS.get(op, op)
            format_str = _COMPARE_OP_FORMAT_OVERRIDES.get(op, '{}{}{}')
            return format_str.format(_xpathify(n1, frame_locals), op, _xpathify(n2, frame_locals))
        raise NotImplementedError, children

    elif ntype == Const:
        return repr(ast_subtree.value)

    elif ntype == And:
        n1, n2 = children
        return '{} and {}'.format(_xpathify(n1, frame_locals), _xpathify(n2, frame_locals))

    elif ntype == Not:
        child, = children
        return 'not({})'.format(_xpathify(child, frame_locals))

    elif ntype == CallFunc:
        if isinstance(children[0], Name) and children[0].name == 'any':
            if _root_level(children[1], frame_locals):
                return _xpathify(children[1], frame_locals)
            return '.' + _xpathify(children[1], frame_locals)
        raise NotImplementedError, children

    else:
        raise NotImplementedError, ntype.__name__


def tests():
    def assert_eq(x, y):
        assert x == y, x
    
    assert (div for div in DOM).gi_frame.f_locals['.0'] == DOM

    assert_eq(xpath(div for div in DOM), '//div')
    assert_eq(xpath(span for div in DOM for span in div), '//div//span')
    assert_eq(xpath(span.cls for div in DOM for span in div), '//div//span/@class')
    assert_eq(xpath(span.text for span in DOM), '//span/text()')
    assert_eq(xpath(span for span in DOM if span.name == 'main'), "//span[@name='main']")
    assert_eq(xpath(div for span in DOM if span.name == 'main' for div in span), "//span[@name='main']//div")
    assert_eq(xpath(div for span in DOM for div in span if span.name == 'main'), "//span[@name='main']//div")
    assert_eq(xpath(div for span in DOM if span.name == 'main' for div in span if div.cls == 'row'), "//span[@name='main']//div[@class='row']")
    #assert_eq(expression(div for span in DOM for div in span if div.cls == 'row' and span.name == 'main'), "//span[@name='main']//div[@class='row']")  tricky case - need to dissect And
    assert_eq(xpath(a for a in DOM if a.href == 'http://www.google.com' and a.name == 'goog'), "//a[@href='http://www.google.com' and @name='goog']")
    assert_eq(xpath(a for a in DOM if '.com' in a.href), "//a[contains(@href, '.com')]")
    assert_eq(xpath(a for a in DOM if '.com' not in a.href), "//a[not(contains(@href, '.com'))]")
    assert_eq(xpath(a for a in DOM if not '.com' in a.href), "//a[not(contains(@href, '.com'))]")
    assert_eq(xpath(div for div in DOM if div.id != 'main'), "//div[@id!='main']")
    assert_eq(xpath(div for div in DOM if not div.id == 'main'), "//div[not(@id='main')]")
    assert_eq(xpath(X for X in DOM if X.name == 'main'), "//*[@name='main']")
    assert_eq(xpath(span for div in DOM for X in div.following_siblings for span in X.children), '//div/following-sibling::*/span')
    assert_eq(xpath(a.href for a in DOM if any(p for p in a.following_siblings)), '//a[./following-sibling::p]/@href')
    assert_eq(xpath(a.href for a in DOM if any(p for p in a.following_siblings if p.id)), '//a[./following-sibling::p[@id]]/@href')
    assert_eq(xpath(X for X in DOM if any(p for p in DOM)), '//*[//p]')

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