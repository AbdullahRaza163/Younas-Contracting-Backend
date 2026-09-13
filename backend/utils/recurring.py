# utils/recurring.py
"""
Recurring-expense generator.

A recurring expense is a top-level Expense row with:
    is_recurring = true
    recurrence_type in ('daily','weekly','monthly')
    parent_expense_id = NULL

This module walks every such rule and creates real child Expense rows
up to today. Idempotent: calling it multiple times will NOT double-post,
because each child is keyed by (parent_expense_id, date).
"""
import calendar
from datetime import date, timedelta
from models import db, Expense
from utils.helpers import generate_id


def _next_date(cursor, rtype, anchor):
    """Return next due date after `cursor` for a rule anchored at `anchor`."""
    rtype = (rtype or '').lower()
    if rtype == 'daily':
        return cursor + timedelta(days=1)
    if rtype == 'weekly':
        return cursor + timedelta(days=7)
    if rtype == 'monthly':
        y, m = cursor.year, cursor.month + 1
        if m > 12:
            m = 1
            y += 1
        d = min(anchor.day, calendar.monthrange(y, m)[1])
        return date(y, m, d)
    return None


def generate_due_recurring_expenses(today=None):
    """
    Walk all recurring rules, create missing child rows up to `today`.
    Returns count of rows created.
    """
    today = today or date.today()

    rules = Expense.query.filter(
        Expense.is_recurring.is_(True),
        Expense.recurrence_type.isnot(None),
        Expense.parent_expense_id.is_(None),
    ).all()

    created = 0
    for rule in rules:
        rtype = (rule.recurrence_type or '').lower()
        if rtype not in ('daily', 'weekly', 'monthly'):
            continue

        anchor = rule.recurrence_start or rule.date
        end    = rule.recurrence_end
        cursor = rule.last_generated or anchor

        guard = 0
        while guard < 1000:
            guard += 1
            nxt = _next_date(cursor, rtype, anchor)
            if not nxt or nxt > today:
                break
            if end and nxt > end:
                break

            exists = Expense.query.filter_by(
                parent_expense_id=rule.id,
                date=nxt,
            ).first()

            if not exists:
                child = Expense(
                    id=generate_id(),
                    date=nxt,
                    site_id=rule.site_id,
                    category=rule.category,
                    description=f"{(rule.description or rule.category)} (auto)",
                    amount=rule.amount,
                    quantity=rule.quantity,
                    unit=rule.unit,
                    is_recurring=False,
                    recurrence_type=None,
                    note=rule.note,
                    parent_expense_id=rule.id,
                    month=nxt.strftime('%Y-%m'),
                )
                db.session.add(child)
                created += 1

            cursor = nxt

        rule.last_generated = cursor

    if created:
        db.session.commit()
    return created