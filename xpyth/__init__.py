from pony.orm.decompiling import Decompiler
from pony.thirdparty.compiler.ast import *
from lxml import etree

import ctypes
import collections


__all__ = 'DOM X xpath query'.split()
__author__ = 'H. Chase Stevens'


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
    frame_globals = g.gi_frame.f_globals
    frame_globals.update(frame_locals)  # Any danger in this?
    expression = _xpathify(ast, frame_globals)
    try:
        etree.XPath(expression)  # Verify syntax
    except etree.XPathSyntaxError:
        raise etree.XPathSyntaxError, expression
    return expression


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

_COMPARE_OP_OPPOSITES = {
    '==': '!=',
    'in': 'not in',
    '>': '<=',
    '<': '>=',
}
_COMPARE_OP_OPPOSITES.update({v: k for k, v in _COMPARE_OP_OPPOSITES.iteritems()})
_COMPARE_OP_OPPOSITES['='] = '!='

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


def _xpathify(ast_subtree, frame_locals, relative=False):
    """Returns a string for a subtree of the AST."""
    ntype = ast_subtree.__class__
    children = ast_subtree.getChildren()

    def rel_xpathify(child, frame_locals, relative_=False):
        '''
        Does it even make sense to have the kwarg here? Does this function make
        sense? Should it just be logic in GenExpr?
        '''
        expr = _xpathify(child, frame_locals, relative_)
        rel = '.' if relative else ''
        return rel + expr

    if ntype == GenExpr:
        child, = children
        return rel_xpathify(child, frame_locals)

    elif ntype == GenExprInner:
        name = children[0]
        fors = children[1:]

        # Rearrange tree if returning booleans, not nodes (all, any)
        return_type = name.__class__
        if return_type in (Compare, Not, And, Or):
            if return_type in (And, Or):
                raise NotImplementedError, "Conjunction and disjunction not supported as return type of generator."
            if return_type == Not:
                name = name.expr
                assert name.__class__ == Compare
                ops = name.ops
                if ops:
                    (op, val), = ops
                    ops = [(_COMPARE_OP_OPPOSITES[op], val)]
            else:
                ops = name.ops
            new_tree = Compare(
                GenExprInner(
                    name.expr,
                    fors
                ),
                ops
            )
            return rel_xpathify(new_tree, frame_locals)

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
            return rel_xpathify(children[0], frame_locals)
        raise NotImplementedError, children

    elif ntype == Compare:
        if len(children) == 3:
            n1, op, n2 = children
            if n2.__class__ == Name:
                # Special case - drag in from outer scope if we're checking inclusion of value in iterable
                local = frame_locals.get(n2.name)
                if isinstance(local, collections.Iterable) and op == 'in':
                    n2 = Const(local)
            if op == 'in' and n2.__class__ == Const and not isinstance(n2.value, str):
                # Special case - checking whether value is in iterable
                comparisons = [Compare(n1, ('==', Const(val))) for val in n2.value]
                return rel_xpathify(Or(comparisons), frame_locals)
            op = _COMPARE_OP_REPLACEMENTS.get(op, op)
            format_str = _COMPARE_OP_FORMAT_OVERRIDES.get(op, '{}{}{}')
            return format_str.format(rel_xpathify(n1, frame_locals), op, rel_xpathify(n2, frame_locals))
        raise NotImplementedError, children

    elif ntype == Const:
        return repr(ast_subtree.value)

    elif ntype == And:
        return ' and '.join(rel_xpathify(child, frame_locals) for child in children)

    elif ntype == Or:
        return ' or '.join(rel_xpathify(child, frame_locals) for child in children)

    elif ntype == Not:
        child, = children
        return 'not({})'.format(rel_xpathify(child, frame_locals))

    elif ntype == CallFunc:
        if isinstance(children[0], Name):
            func_name = children[0].name
            is_relative = lambda: not _root_level(children[1], frame_locals)
            if func_name == 'any':
                return rel_xpathify(children[1], frame_locals, is_relative())
            if func_name == 'len':
                return 'count({})'.format(rel_xpathify(children[1], frame_locals, is_relative()))
            elif func_name == 'all':
                # Need to change (\all x. P) to (\not \exists x. \not P)
                genexprinner = children[1].getChildren()[0]
                assert genexprinner.__class__ == GenExprInner
                name, genexprfor = genexprinner.getChildren()
                gef_assname, gef_name = genexprfor.getChildren()[:2]
                gef_ifs = genexprfor.ifs
                new_tree = Not(
                    GenExpr(
                        GenExprInner(
                            name, 
                            [GenExprFor(
                                gef_assname,
                                gef_name, 
                                [Not(gef_ifs[0])] if gef_ifs else []
                            )]
                        )
                    )
                )
                return rel_xpathify(new_tree, frame_locals, is_relative())
                raise NotImplementedError, children
        raise NotImplementedError, children

    else:
        raise NotImplementedError, ntype.__name__
