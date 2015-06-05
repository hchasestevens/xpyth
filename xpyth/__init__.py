from pony.orm.decompiling import Decompiler
from pony.thirdparty.compiler.ast import *
from lxml import etree

import ctypes
import collections
import functools


__all__ = 'DOM X xpath query'.split()
__author__ = 'H. Chase Stevens'


DEBUG = False


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
    expression = _handle_genexpr(ast, frame_globals)
    try:
        etree.XPath(expression)  # Verify syntax
    except etree.XPathSyntaxError:
        raise etree.XPathSyntaxError, expression
    return expression


def query(g):
    """Queries a DOM tree (lxml Element)."""
    try:
        dom = next(g.gi_frame.f_locals['.0']).getparent()  # lxml  # TODO: change for selenium etc.
    except StopIteration:
        return []  # copying what lxml does
    
    # Magic to convert our generator into a DOM-generator (http://pydev.blogspot.co.uk/2014/02/changing-locals-of-frame-frameflocals.html)
    g.gi_frame.f_locals['.0'] = DOM
    ctypes.pythonapi.PyFrame_LocalsToFast(ctypes.py_object(g.gi_frame), ctypes.c_int(0))
    
    expression = '.' + xpath(g)

    method_names = (
        'xpath',  # lxml ElementTree
        'findall',  # xml ElementTree
        'find_elements_by_xpath',  # selenium WebDriver/WebElement
    )
    for method_name in method_names:
        try:
            xpath_method = getattr(dom, method_name)
            break
        except AttributeError:
            pass
    else:
        raise NotImplementedError, dom.__class__.__name__

    return xpath_method(expression)


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


def _subtree_handler_factory():
    _SUBTREE_HANDLERS = {}
    
    def _subtree_handler(*ntypes, **kwargs):
        supply_ast = kwargs.get('supply_ast', False)
        def decorator(f):
            @functools.wraps(f)
            def wrapper(ast_subtree, frame_locals, relative=False):
                children = ast_subtree.getChildren()
                result = f(ast_subtree if supply_ast else children, frame_locals, relative)
                if DEBUG:
                    print f.__name__
                    print result
                    print
                return result
            for ntype in ntypes:
                _SUBTREE_HANDLERS[ntype] = wrapper
            return wrapper
        return decorator

    def _dispatch(subtree):
        """Choose appropriate subtree handler for subtree type"""
        ntype = subtree.__class__
        try:
            return functools.partial(_SUBTREE_HANDLERS[ntype], subtree)
        except KeyError:
            raise NotImplementedError, ntype.__name__
    return _subtree_handler, _dispatch

_subtree_handler, _dispatch = _subtree_handler_factory()


@_subtree_handler(GenExpr)
def _handle_genexpr(children, frame_locals, relative):
    child, = children
    rel = '.' if relative else ''
    assert child.__class__ == GenExprInner  # TODO: remove
    return rel + _handle_genexprinner(child, frame_locals)


@_subtree_handler(GenExprInner)
def _handle_genexprinner(children, frame_locals, relative):
    name = children[0]
    fors = children[1:]
    rel = '.' if relative else ''

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
        return rel + _dispatch(new_tree)(frame_locals)  # TODO: replace with Compare, since we know this

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
        
        # decompose Ands
        ifs = for_.ifs[:]
        for if_ in ifs:
            try:
                test = if_.test
            except AttributeError:  # e.g. Not has no test attr
                continue
            if isinstance(test, And):
                for_.ifs.remove(if_)
                for_.ifs.extend([GenExprIf(node) for node in test.nodes])

        # shuffle conditionals around so that they test the appropriate level
        ifs = for_.ifs[:]
        for if_ in ifs:
            highest_src = _get_highest_src(if_, ranked_src_names)
            if not highest_src:
                continue
            highest_src, = highest_src
            if highest_src != for_src:
                for_srcs[highest_src].ifs.append(if_)
                try:
                    for_.ifs.remove(if_)
                except ValueError:  # we constructed this conditional artificially
                    pass

        # conjoin any loose conditionals
        if len(for_.ifs) > 1:
            for_.ifs = [reduce(lambda x, y: And([x, y]), for_.ifs)]

    assert all(for_.__class__ == GenExprFor for for_ in fors)  # TODO: remove
    fors = ''.join([_handle_genexprfor(for_, frame_locals) for for_ in fors])
    if return_type in (Getattr, Sub):
        return '{}/{}'.format(fors, _dispatch(name)(frame_locals))
    return fors


@_subtree_handler(Name, AssName, supply_ast=True)
def _handle_name(ast_subtree, frame_locals, relative=False):
    name = ast_subtree.name
    if name == '.0':
        return '.'
    if name == 'X':
        return '*'
    return name


@_subtree_handler(GenExprFor)
def _handle_genexprfor(children, frame_locals, relative):
    name, src = children[:2]
    conds = children[2:]
    sep = '//'
    if isinstance(src, Getattr):
        sep = _GENEXPRFOR_GETATTR_SEP_OVERRIDES.get(src.attrname, '//')
    if not conds:
        # TODO: determine type of name
        return '{}{}'.format(sep, _dispatch(name)(frame_locals))  # slashes are contingent on src
    # TODO: determine type of conds
    return '{}{}[{}]'.format(sep, _dispatch(name)(frame_locals), _dispatch(conds[0])(frame_locals))  # 0?


@_subtree_handler(Getattr)
def _handle_getattr(children, frame_locals, relative):
    name, attr = children
    attr = _ATTR_REPLACEMENTS.get(attr, attr)
    # this might need to be context-sensitive... Almost assuredly, actually
    # consider: .//div/@class, .//div[./@class='x']
    return _ATTR_FORMAT_OVERRIDES.get(attr, '@{}').format(attr)


@_subtree_handler(GenExprIf)
def _handle_genexprif(children, frame_locals, relative):
    rel = '.' if relative else ''
    if len(children) == 1:
        return _dispatch(children[0])(frame_locals)  # TODO: see if child type is consistent
    raise NotImplementedError, children


@_subtree_handler(Compare)
def _handle_compare(children, frame_locals, relative):
    rel = '.' if relative else ''

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
            return rel + _handle_or(Or(comparisons), frame_locals)
        op = _COMPARE_OP_REPLACEMENTS.get(op, op)
        format_str = _COMPARE_OP_FORMAT_OVERRIDES.get(op, '{}{}{}')
        return format_str.format(rel + _dispatch(n1)(frame_locals), op, rel + _dispatch(n2)(frame_locals))
    raise NotImplementedError, children


@_subtree_handler(Const, supply_ast=True)
def _handle_const(ast_subtree, frame_locals, relative=False):
    return repr(ast_subtree.value)


@_subtree_handler(And)
def _handle_and(children, frame_locals, relative):
    rel = '.' if relative else ''
    return ' and '.join(rel + _dispatch(child)(frame_locals) for child in children)


@_subtree_handler(Or)
def _handle_or(children, frame_locals, relative):
    rel = '.' if relative else ''
    return ' or '.join(rel + _dispatch(child)(frame_locals) for child in children)


@_subtree_handler(Not)
def _handle_not(children, frame_locals, relative):
    child, = children
    rel = '.' if relative else ''
    return 'not({})'.format(rel + _dispatch(child)(frame_locals))


@_subtree_handler(Sub)
def _handle_sub(children, frame_locals, relative):
    return '-'.join(_dispatch(child)(frame_locals) for child in children)


@_subtree_handler(CallFunc)
def _handle_callfunc(children, frame_locals, relative):
    rel = '.' if relative else ''
    if isinstance(children[0], Name):
        func_name = children[0].name
        is_relative = lambda: not _root_level(children[1], frame_locals)
        if func_name == 'any':
            return rel + _dispatch(children[1])(frame_locals, is_relative())
        if func_name == 'len':
            return 'count({})'.format(rel + _dispatch(children[1])(frame_locals, is_relative()))
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
            return rel + _handle_not(new_tree, frame_locals, is_relative())
            raise NotImplementedError, children
    raise NotImplementedError, children
