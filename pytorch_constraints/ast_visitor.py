import ast


class FunDefFindingVisitor(ast.NodeVisitor):
    def __init__(self):
        super(ast.NodeVisitor).__init__()

    def visit_Module(self, node):
        return self.visit(node.body[0])

    def visit_Assign(self, node):
        return self.visit(node.value)

    def visit_Call(self, node):
        assert(node.func.id == 'constraint')
        return self.visit(node.args[0])

    def visit_Lambda(self, node):
        return node

    def visit_FunctionDef(self, node):
        return node


class TreeNode:
    def __init__(self, name, children):
        self.name = name
        self.children = children

    def __str__(self):
        arg_str = "(" + ",".join([str(c) for c in self.children]) + ")" if len(self.children) > 0 else ""
        return self.name + arg_str

    def as_bool(self):
        return self

    def tnorm(self, probs):
        print(self)
        raise NotImplementedError

    def __eq__(self, obj):
        return (type(obj) == type(self) and
                self.name == obj.name and self.children == obj.children)


class BinaryOp(TreeNode):
    def __init__(self, name, left, right):
        self.left = left
        self.right = right
        super().__init__(name, [left, right])


class And(BinaryOp):
    def __init__(self, left, right):
        super().__init__("And", left, right)

    def tnorm(self, probs):
        lv = self.left.tnorm(probs)
        rv = self.right.tnorm(probs)
        return lv * rv


class Or(BinaryOp):
    def __init__(self, left, right):
        super().__init__("Or", left, right)

    def tnorm(self, probs):
        lv = self.left.tnorm(probs)
        rv = self.right.tnorm(probs)
        return lv + rv - lv * rv


class UnaryOp(TreeNode):
    def __init__(self, name, operand):
        self.operand = operand
        super().__init__(name, [operand])


class Not(UnaryOp):
    def __init__(self, operand):
        super().__init__("Not", operand)

    def tnorm(self, probs):
        return 1.0 - self.operand.tnorm(probs)


class IsEq(BinaryOp):
    def __init__(self, left, right):
        super().__init__('Eq', left, right)

    def tnorm(self, probs):
        if isinstance(self.left, VarUse) and isinstance(self.right, Const):
            return probs[self.left.index][self.right.value]
        elif isinstance(self.left, Const) and isinstance(self.right, VarUse):
            return probs[self.left.index][self.right.value]
        elif isinstance(self.left, Const) and isinstance(self.right, Const):
            return 1.0 if self.left.value == self.right.value else 0.0
        elif isinstance(self.left, VarUse) and isinstance(self.right, VarUse):
            return (probs[self.left.index, :]*probs[self.right.index, :]).sum()
        else:
            raise NotImplementedError


class Const(TreeNode):
    def __init__(self, value):
        self.value = value
        self.is_bool = isinstance(value, bool)
        super().__init__(str(value), [])

    def as_bool(self):
        return self if self.is_bool else Const(bool(self.value))

    def tnorm(self, probs):
        return 1.0 if self.value == self.value else 0.0


class VarUse(TreeNode):
    def __init__(self, index):
        self.index = index
        super().__init__('y[' + str(self.index) + "]", [])

    def as_bool(self):
        return Not(IsEq(self, Const(0)))


class LogicExpressionVisitor(ast.NodeVisitor):

    def __init__(self):
        super(ast.NodeVisitor).__init__()

    def generic_visit(self, node):
        print(ast.dump(node))
        raise NotImplementedError

    def visit_FunctionDef(self, node):
        # TODO: handle multiple lines, and do something with arguments?
        body_tree = self.visit(node.body[0])
        return body_tree

    def visit_Lambda(self, node):
        # Same as FunctionDef?
        body_tree = self.visit(node.body)
        return body_tree

    def visit_Return(self, node):
        return self.visit(node.value).as_bool()

    def visit_UnaryOp(self, node):
        supported = {
            ast.Not: (lambda opr: Not(opr.as_bool()))
        }
        op_func = supported[type(node.op)]
        opr = self.visit(node.operand)
        return op_func(opr)

    def visit_Subscript(self, node):
        # TODO check node.value is the variable?
        return VarUse(node.slice.value.n)

    def visit_NameConstant(self, node):
        #deprecated in 3.8
        return Const(node.value)

    def visit_Num(self, node):
        #deprecated in 3.8
        return Const(node.n)

    def visit_Constant(self, node):
        return Const(node.value)

    def visit_BoolOp(self, node):
        supported = {
            ast.And: (lambda left, right: And(left.as_bool(), right.as_bool())),
            ast.Or: (lambda left, right: Or(left.as_bool(), right.as_bool()))
        }
        op_func = supported[type(node.op)]
        ltree = self.visit(node.values[0])
        rtree = self.visit(node.values[1])
        return op_func(ltree, rtree)

    def visit_Compare(self, node):
        supported = {
            ast.Eq: (lambda left, right: IsEq(left, right)),
            ast.NotEq: (lambda left, right: Not(IsEq(left, right)))
        }
        assert(len(node.ops))
        op_func = supported[type(node.ops[0])]
        ltree = self.visit(node.left)
        assert(len(node.comparators))
        rtree = self.visit(node.comparators[0])
        return op_func(ltree, rtree)
