# coding: utf-8
from __future__ import unicode_literals

from yargy.visitor import Visitor
from yargy.dot import (
    style,
    DotTransformator,
    BLUE,
    ORANGE,
    RED,
    PURPLE,
    GREEN,
    GRAY,
    DARKGRAY
)

from yargy.predicates import is_predicate
from .constructors import (
    is_rule,
    Production,
    EmptyProduction,
    Rule,
    OrRule,
    ExtendedRule,
    OptionalRule,
    RepeatableRule,
    BoundedRule,
    MinBoundedRule,
    MaxBoundedRule,
    MinMaxBoundedRule,
    RepeatableOptionalRule,
    NamedRule,
    InterpretationRule,
    RelationRule,
    ForwardRule,
    EmptyRule,
    PipelineRule
)


class InplaceRuleTransformator(Visitor):
    def __call__(self, root):
        for item in root.walk(types=(Rule, Production)):
            self.visit(item)
        return self.visit(root)

    def visit_term(self, item):
        return item

    def visit_Production(self, item):
        item.terms = [self.visit_term(_) for _ in item.terms]
        return item

    def visit_EmptyProduction(self, item):
        return item

    def visit_PipelineProduction(self, item):
        return item

    def visit_Rule(self, item):
        return item


class RuleTransformator(Visitor):
    def __init__(self):
        self.visited = {}

    def __call__(self, root):
        for item in root.walk(types=ForwardRule):
            if item.rule:
                item.define(self.visit(item.rule))
        return self.visit(root)

    def visit(self, item):
        item_id = id(item)
        if item_id in self.visited:
            return self.visited[item_id]
        else:
            item = self.resolve_method(item)(item)
            self.visited[item_id] = item
            return item

    def visit_term(self, item):
        if is_rule(item):
            return self.visit(item)
        else:
            return item

    def visit_Production(self, item):
        return Production(
            [self.visit_term(_) for _ in item.terms],
            item.main
        )

    def visit_EmptyProduction(self, item):
        return item

    def visit_PipelineProduction(self, item):
        return item

    def visit_Rule(self, item):
        return Rule([self.visit(_) for _ in item.productions])

    def visit_OrRule(self, item):
        return OrRule([self.visit(_) for _ in item.rules])

    def visit_OptionalRule(self, item):
        return OptionalRule(self.visit(item.rule))

    def visit_RepeatableRule(self, item):
        return RepeatableRule(self.visit(item.rule))

    def visit_RepeatableOptionalRule(self, item):
        return RepeatableOptionalRule(self.visit(item.rule))

    def visit_MinBoundedRule(self, item):
        return MinBoundedRule(self.visit(item.rule), item.min)

    def visit_MaxBoundedRule(self, item):
        return MaxBoundedRule(self.visit(item.rule), item.max)

    def visit_MinMaxBoundedRule(self, item):
        return MinMaxBoundedRule(self.visit(item.rule), item.min, item.max)

    def visit_NamedRule(self, item):
        return NamedRule(self.visit(item.rule), item.name)

    def visit_InterpretationRule(self, item):
        return InterpretationRule(self.visit(item.rule), item.interpretator)

    def visit_RelationRule(self, item):
        return RelationRule(self.visit(item.rule), item.relation)

    def visit_ForwardRule(self, item):
        return item

    def visit_EmptyRule(self, item):
        return item

    def visit_PipelineRule(self, item):
        return item


class ActivateTransformator(InplaceRuleTransformator):
    def __init__(self, context):
        super(ActivateTransformator, self).__init__()
        self.context = context

    def visit_term(self, item):
        if is_predicate(item):
            return item.activate(self.context)
        else:
            return item

    def visit_PipelineRule(self, item):
        item.pipeline = item.pipeline.activate(self.context)
        return item


class SquashExtendedTransformator(RuleTransformator):
    def visit_RepeatableRule(self, item):
        child = item.rule
        if isinstance(child, (OptionalRule, RepeatableOptionalRule)):
            return self.visit(RepeatableOptionalRule(child.rule))
        elif isinstance(child, (RepeatableRule, BoundedRule)):
            return self.visit(RepeatableRule(child.rule))
        else:
            return RepeatableRule(self.visit(child))

    def visit_OptionalRule(self, item):
        child = item.rule
        if isinstance(child, (RepeatableRule, RepeatableOptionalRule)):
            return self.visit(RepeatableOptionalRule(child.rule))
        elif isinstance(child, OptionalRule):
            return self.visit(OptionalRule(child.rule))
        else:
            return OptionalRule(self.visit(child))

    def visit_RepeatableOptionalRule(self, item):
        child = item.rule
        if isinstance(child, (RepeatableRule, BoundedRule,
                              OptionalRule, RepeatableOptionalRule)):
            return self.visit(RepeatableOptionalRule(child.rule))
        else:
            return RepeatableOptionalRule(self.visit(child))

    def visit_BoundedRule(self, item):
        child = item.rule
        if isinstance(child, RepeatableRule):
            return self.visit(RepeatableRule(child.rule))
        elif isinstance(child, RepeatableOptionalRule):
            return self.visit(RepeatableOptionalRule(child.rule))
        raise TypeError

    def visit_MinBoundedRule(self, item):
        child = item.rule
        if isinstance(child, (RepeatableRule, RepeatableOptionalRule)):
            return self.visit_BoundedRule(item)
        elif isinstance(child, OptionalRule):
            return self.visit(OptionalRule(MinBoundedRule(child.rule, item.min)))
        else:
            return MinBoundedRule(self.visit(child), item.min)

    def visit_MaxBoundedRule(self, item):
        child = item.rule
        if isinstance(child, (RepeatableRule, RepeatableOptionalRule)):
            return self.visit_BoundedRule(item)
        elif isinstance(child, OptionalRule):
            return self.visit(OptionalRule(MaxBoundedRule(child.rule, item.max)))
        else:
            return MaxBoundedRule(self.visit(child), item.max)

    def visit_MinMaxBoundedRule(self, item):
        child = item.rule
        if isinstance(child, (RepeatableRule, RepeatableOptionalRule)):
            return self.visit_BoundedRule(item)
        elif isinstance(child, OptionalRule):
            return self.visit(OptionalRule(MinMaxBoundedRule(
                child.rule, item.min, item.max
            )))
        else:
            return MinMaxBoundedRule(self.visit(child), item.min, item.max)


class FlattenTransformator(RuleTransformator):
    def visit_term(self, item):
        if type(item) is Rule:
            productions = item.productions
            if len(productions) == 1:
                terms = productions[0].terms
                if len(terms) == 1:
                    term = terms[0]
                    return self.visit_term(term)
        return super(FlattenTransformator, self).visit_term(item)

    def visit_Production(self, item):
        terms = item.terms
        if len(terms) == 1:
            term = terms[0]
            if type(term) is Rule:
                productions = term.productions
                if len(productions) == 1:
                    production = productions[0]
                    return self.visit(production)
        return super(FlattenTransformator, self).visit_Production(item)


class ReplaceOrTransformator(RuleTransformator):
    def visit_OrRule(self, item):
        return Rule([Production([self.visit(_)]) for _ in item.rules])


class ReplaceEmptyTransformator(RuleTransformator):
    def visit_EmptyRule(self, item):
        return Rule([EmptyProduction()])


def bound(item, count):
    from yargy.api import rule, or_

    if count == 1:
        return item
    else:
        return or_(
            rule(item, bound(item, count - 1)),
            item
        )


def repeat(item, count):
    return [item for _ in range(count)]


class ReplaceExtendedTransformator(RuleTransformator):
    def visit_RepeatableRule(self, item):
        from yargy.api import forward, or_, rule

        child = self.visit(item.rule)
        temp = forward()
        return temp.define(
            or_(
                rule(child, temp),
                child
            )
        )

    def visit_OptionalRule(self, item):
        from yargy.api import or_, empty

        child = self.visit(item.rule)
        return or_(child, empty())

    def visit_RepeatableOptionalRule(self, item):
        from yargy.api import forward, or_, rule, empty

        child = self.visit(item.rule)
        temp = forward()
        return temp.define(
            or_(
                rule(child, temp),
                child,
                empty(),
            )
        )

    def visit_MinBoundedRule(self, item):
        from yargy.api import rule

        items = repeat(item.rule, item.min - 1) + [
            self.visit_RepeatableRule(item)
        ]
        return rule(*items)

    def visit_MaxBoundedRule(self, item):
        return bound(item.rule, item.max)

    def visit_MinMaxBoundedRule(self, item):
        from yargy.api import rule

        child, min, max = item
        items = repeat(child, min - 1) + [
            bound(child, max - min + 1)
        ]
        return rule(*items)


class DotRuleTransformator(DotTransformator, InplaceRuleTransformator):
    def visit_Predicate(self, item):
        self.style(
            item,
            style(label=item.label)
        )

    def visit_Production(self, item):
        self.graph.add_node(
            item,
            style(label='Production', fillcolor=BLUE)
        )
        for index, child in enumerate(item.children):
            styling = (
                style(color=DARKGRAY)
                if item.main > 0 and item.main == index
                else None
            )
            self.graph.add_edge(
                item, child,
                style=styling
            )

    def visit_EmptyProduction(self, item):
        self.style(
            item,
            style(label='EmptyProduction')
        )

    def visit_PipelineProduction(self, item):
        self.style(
            item,
            style(label='PipelineProduction', fillcolor=BLUE)
        )

    def visit_Rule(self, item):
        self.style(
            item,
            style(label='Rule', fillcolor=BLUE)
        )

    def visit_OrRule(self, item):
        self.style(
            item,
            style(label='Or', fillcolor=BLUE)
        )

    def visit_OptionalRule(self, item):
        self.style(
            item,
            style(label='Optional', fillcolor=ORANGE)
        )

    def visit_RepeatableRule(self, item):
        self.style(
            item,
            style(label='Repeatable', fillcolor=ORANGE)
        )

    def visit_RepeatableOptionalRule(self, item):
        self.style(
            item,
            style(label='RepeatableOptional', fillcolor=ORANGE)
        )

    def visit_NamedRule(self, item):
        self.style(
            item,
            style(label=item.name, fillcolor=RED)
        )

    def visit_InterpretationRule(self, item):
        self.style(
            item,
            style(label=item.interpretator.label, fillcolor=GREEN)
        )

    def visit_RelationRule(self, item):
        self.style(
            item,
            style(label=item.relation.label, fillcolor=PURPLE)
        )

    def visit_ForwardRule(self, item):
        self.style(
            item,
            style(label='Forward', fillcolor=PURPLE)
        )

    def visit_EmptyRule(self, item):
        self.style(
            item,
            style(label='Empty')
        )

    def visit_PipelineRule(self, item):
        self.style(
            item,
            style(label=item.pipeline.label, fillcolor=PURPLE)
        )

    def visit_BNFRule(self, item):
        self.style(
            item,
            style(label=item.label, fillcolor=GREEN)
        )
