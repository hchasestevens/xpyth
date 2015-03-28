from pony.orm.decompiling import Decompiler
from pony.thirdparty.compiler.ast import *
from lxml import etree

import ctypes


class _DOM(object):
    def __iter__(self):
        return self
    def next():
        return self

DOM = _DOM()


def expression(g):
    """Returns XPath expression corresponding to generator."""
    assert g.gi_frame.f_locals['.0'] == DOM, "Only root-level expressions are supported."
    ast = Decompiler(g.gi_code).ast
    return _xpathify(ast)


def query(g):
    """Queries a DOM tree (lxml Element)."""
    try:
        dom = next(g.gi_frame.f_locals['.0']).getparent()
    except StopIteration:
        return []  # copying what lxml does
    
    # Magic to convert our generator into a DOM-generator (http://pydev.blogspot.co.uk/2014/02/changing-locals-of-frame-frameflocals.html)
    g.gi_frame.f_locals['.0'] = DOM
    ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(g.gi_frame), ctypes.c_int(0))
    
    xpath = '.' + expression(g)
    return dom.xpath(xpath)



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


def _xpathify(ast_subtree):
    """Returns a string for a subtree of the AST."""
    ntype = ast_subtree.__class__
    children = ast_subtree.getChildren()

    if ntype == GenExpr:
        child, = children
        return _xpathify(child)

    elif ntype == GenExprInner:
        name = children[0]
        fors = children[1:]
        fors = ''.join(map(_xpathify, fors))
        if isinstance(name, Getattr):
            return '{}/{}'.format(fors, _xpathify(name))
        return fors

    elif ntype in (Name, AssName):
        name = ast_subtree.name
        if name == '.0':
            return '.'
        return name

    elif ntype == GenExprFor:
        name, src = children[:2]
        conds = children[2:]
        if not conds:
            return '//{}'.format(_xpathify(name))
        return '//{}[{}]'.format(_xpathify(name), _xpathify(conds[0]))  # 0?

    elif ntype == Getattr:
        name, attr = children
        attr = _ATTR_REPLACEMENTS.get(attr, attr)
        # this might need to be context-sensitive... Almost assuredly, actually
        # consider: .//div/@class, .//div[./@class='x']
        return _ATTR_FORMAT_OVERRIDES.get(attr, '@{}').format(attr)

    elif ntype == GenExprIf:
        if len(children) == 1:
            return _xpathify(children[0])
        raise NotImplementedError, children

    elif ntype == Compare:
        if len(children) == 3:
            n1, op, n2 = children
            op = _COMPARE_OP_REPLACEMENTS.get(op, op)
            format_str = _COMPARE_OP_FORMAT_OVERRIDES.get(op, '{}{}{}')
            return format_str.format(_xpathify(n1), op, _xpathify(n2))
        raise NotImplementedError, children

    elif ntype == Const:
        return repr(ast_subtree.value)

    elif ntype == And:
        n1, n2 = children
        return '{} and {}'.format(_xpathify(n1), _xpathify(n2))

    elif ntype == Not:
        child, = children
        return 'not({})'.format(_xpathify(child))

    else:
        raise NotImplementedError, ntype.__name__


def tests():
    def assert_eq(x, y):
        assert x == y, x
    
    assert (div for div in DOM).gi_frame.f_locals['.0'] == DOM
    
    assert_eq(expression(div for div in DOM), '//div')
    assert_eq(expression(span for div in DOM for span in div), '//div//span')
    assert_eq(expression(span.cls for div in DOM for span in div), '//div//span/@class')
    assert_eq(expression(span.text for span in DOM), '//span/text()')
    assert_eq(expression(span for span in DOM if span.name == 'main'), "//span[@name='main']")
    assert_eq(expression(div for span in DOM if span.name == 'main' for div in span), "//span[@name='main']//div")
    # assert_eq(expression(div for span in DOM for div in span if span.name == 'main'), "//span[@name='main']//div")  :) tricky case
    assert_eq(expression(div for span in DOM if span.name == 'main' for div in span if div.cls == 'row'), "//span[@name='main']//div[@class='row']")
    # assert_eq(expression(div for span in DOM for div in span if div.cls == 'row' and span.name == 'main'), "//span[@name='main']//div[@class='row']")  :) another tricky case
    assert_eq(expression(a for a in DOM if a.href == 'http://www.google.com' and a.name == 'goog'), "//a[@href='http://www.google.com' and @name='goog']")
    assert_eq(expression(a for a in DOM if '.com' in a.href), "//a[contains(@href, '.com')]")
    assert_eq(expression(a for a in DOM if '.com' not in a.href), "//a[not(contains(@href, '.com'))]")
    assert_eq(expression(a for a in DOM if not '.com' in a.href), "//a[not(contains(@href, '.com'))]")
    assert_eq(expression(div for div in DOM if div.id != 'main'), "//div[@id!='main']")
    assert_eq(expression(div for div in DOM if not div.id == 'main'), "//div[not(@id='main')]")

    tree = etree.fromstring('''
    <html>
        <div id='main' class='main'>
            <a href='http://www.google.com'>Google</a>
            <a href='http://www.chasestevens.com'>Not Google</a>
            <p>Lorem ipsum</p>
        </div>
    </html>
    ''')
    assert len(query(a for a in tree)) == 2


if __name__ == '__main__':
    tests()