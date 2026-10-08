# -*- coding: utf-8 -*-
# @Author: Your name
# @Date:   2026-10-08 16:12:53
# @Last Modified by:   Your name
# @Last Modified time: 2026-10-08 16:52:58
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Iterable
from uuid import uuid4

import streamlit as st
import pandas as pd


CENT = Decimal("0.01")


class ExpenseCategory(str, Enum):
	FOOD = "Food"
	TRANSPORT = "Transport"
	UTILITIES = "Utilities"
	ENTERTAINMENT = "Entertainment"
	HEALTH = "Health"
	OTHER = "Other"

	@classmethod
	def from_value(cls, value: ExpenseCategory | str) -> ExpenseCategory:
		raw_value = getattr(value, "value", value)
		normalized = str(raw_value).strip().casefold()
		for category in cls:
			if category.value.casefold() == normalized:
				return category
		options = ", ".join(category.value for category in cls)
		raise ValueError(f"Choose a category from: {options}.")


@dataclass(frozen=True, slots=True)
class Expense:
	id: str
	date: date
	category: ExpenseCategory
	amount: Decimal
	description: str

	def __post_init__(self) -> None:
		if not self.id.strip():
			raise ValueError("Expense ID cannot be blank.")
		if not isinstance(self.date, date):
			raise ValueError("Expense date must be a date.")
		object.__setattr__(self, "category", ExpenseCategory.from_value(self.category))
		try:
			amount = Decimal(str(self.amount).strip())
		except (InvalidOperation, ValueError):
			raise ValueError("Amount must be a valid number.") from None
		if not amount.is_finite() or amount <= 0:
			raise ValueError("Amount must be a positive finite number.")
		if amount != amount.quantize(CENT):
			raise ValueError("Amount cannot have more than two decimal places.")
		object.__setattr__(self, "amount", amount)
		object.__setattr__(self, "description", str(self.description).strip())

	def to_dict(self) -> dict[str, str]:
		return {
			"id": self.id,
			"date": self.date.isoformat(),
			"category": self.category.value,
			"amount": format(self.amount, ".2f"),
			"description": self.description,
		}

	@classmethod
	def from_dict(cls, data: dict[str, str]) -> Expense:
		try:
			expense_date = date.fromisoformat(data["date"])
			return cls(
				id=data["id"],
				date=expense_date,
				category=ExpenseCategory.from_value(data["category"]),
				amount=Decimal(data["amount"]),
				description=data.get("description", ""),
			)
		except (KeyError, TypeError, InvalidOperation) as error:
			raise ValueError("Expense data is incomplete or invalid.") from error


class ExpenseManager:
	def __init__(self) -> None:
		self._expenses: dict[str, Expense] = {}

	def create_expense(
		self,
		expense_date: date,
		category: ExpenseCategory | str,
		amount: Decimal | str,
		description: str,
	) -> Expense:
		expense = Expense(
			id=str(uuid4()),
			date=expense_date,
			category=ExpenseCategory.from_value(category),
			amount=Decimal(str(amount)),
			description=description,
		)
		self._expenses[expense.id] = expense
		return expense

	def get_expense(self, expense_id: str) -> Expense | None:
		return self._expenses.get(expense_id)

	def list_expenses(self) -> list[Expense]:
		return sorted(
			self._expenses.values(),
			key=lambda expense: (expense.date, expense.id),
			reverse=True,
		)

	def update_expense(
		self,
		expense_id: str,
		expense_date: date,
		category: ExpenseCategory | str,
		amount: Decimal | str,
		description: str,
	) -> Expense:
		if expense_id not in self._expenses:
			raise KeyError(f"Expense {expense_id} does not exist.")
		expense = Expense(
			id=expense_id,
			date=expense_date,
			category=ExpenseCategory.from_value(category),
			amount=Decimal(str(amount)),
			description=description,
		)
		self._expenses[expense_id] = expense
		return expense

	def delete_expense(self, expense_id: str) -> bool:
		return self._expenses.pop(expense_id, None) is not None

	def filter_expenses(
		self,
		start_date: date | None = None,
		end_date: date | None = None,
	) -> list[Expense]:
		if start_date is not None and end_date is not None and start_date > end_date:
			raise ValueError("Start date must be on or before end date.")
		return [
			expense
			for expense in self.list_expenses()
			if (start_date is None or expense.date >= start_date)
			and (end_date is None or expense.date <= end_date)
		]

	@staticmethod
	def get_total_spending(expenses: Iterable[Expense]) -> Decimal:
		return sum((expense.amount for expense in expenses), Decimal("0.00"))

	@staticmethod
	def get_category_totals(
		expenses: Iterable[Expense],
	) -> dict[ExpenseCategory, Decimal]:
		totals = {category: Decimal("0.00") for category in ExpenseCategory}
		for expense in expenses:
			category = ExpenseCategory.from_value(expense.category)
			totals[category] += expense.amount
		return totals


class ExpenseSession:
	_STATE_KEY = "expense_manager_v1"

	@staticmethod
	def get_manager() -> ExpenseManager:
		manager = st.session_state.get(ExpenseSession._STATE_KEY)
		if manager is None:
			manager = ExpenseManager()
			st.session_state[ExpenseSession._STATE_KEY] = manager
		return manager


def render_sidebar_filters(
	manager: ExpenseManager,
) -> tuple[date | None, date | None]:
	with st.sidebar:
		st.header("Filters")
		filter_enabled = st.checkbox(
			"Filter by date range", key="date_filter_enabled"
		)
		if not filter_enabled:
			return None, None

		existing_expenses = manager.list_expenses()
		default_start = min(
			(expense.date for expense in existing_expenses), default=date.today()
		)
		default_end = max(
			(expense.date for expense in existing_expenses), default=date.today()
		)
		start_date = st.date_input(
			"From", value=default_start, key="filter_start_date"
		)
		end_date = st.date_input(
			"Through", value=default_end, key="filter_end_date"
		)
		return start_date, end_date


def render_expense_form(manager: ExpenseManager) -> None:
	st.subheader("Add expense")
	with st.form("add_expense_form", clear_on_submit=True):
		date_column, category_column, amount_column = st.columns(3)
		with date_column:
			expense_date = st.date_input("Date", value=date.today(), key="add_date")
		with category_column:
			category = st.selectbox(
				"Category", list(ExpenseCategory), format_func=lambda item: item.value
			)
		with amount_column:
			amount = st.text_input("Amount", placeholder="0.00")
		description = st.text_input("Description", max_chars=200)
		submitted = st.form_submit_button("Add expense", type="primary")

	if submitted:
		try:
			manager.create_expense(expense_date, category, amount, description)
		except (ValueError, InvalidOperation) as error:
			st.error(str(error))
		else:
			st.toast("Expense added.")
			st.rerun()


def _render_edit_form(manager: ExpenseManager, expense_id: str) -> None:
	expense = manager.get_expense(expense_id)
	if expense is None:
		st.session_state.pop("editing_expense_id", None)
		return

	st.subheader("Edit expense")
	category_default = ExpenseCategory.from_value(expense.category)
	with st.form(f"edit_expense_form_{expense.id}"):
		date_column, category_column, amount_column = st.columns(3)
		with date_column:
			expense_date = st.date_input(
				"Date", value=expense.date, key=f"edit_date_{expense.id}"
			)
		with category_column:
			category = st.selectbox(
				"Category",
				list(ExpenseCategory),
				index=list(ExpenseCategory).index(category_default),
				format_func=lambda item: item.value,
				key=f"edit_category_{expense.id}",
			)
		with amount_column:
			amount = st.text_input(
				"Amount",
				value=format(expense.amount, ".2f"),
				key=f"edit_amount_{expense.id}",
			)
		description = st.text_input(
			"Description",
			value=expense.description,
			max_chars=200,
			key=f"edit_description_{expense.id}",
		)
		save_column, cancel_column = st.columns(2)
		with save_column:
			save = st.form_submit_button("Save changes", type="primary")
		with cancel_column:
			cancel = st.form_submit_button("Cancel")

	if cancel:
		st.session_state.pop("editing_expense_id", None)
		st.rerun()
	if save:
		try:
			manager.update_expense(
				expense.id, expense_date, category, amount, description
			)
		except (KeyError, ValueError, InvalidOperation) as error:
			st.error(str(error))
		else:
			st.session_state.pop("editing_expense_id", None)
			st.toast("Expense updated.")
			st.rerun()


def _expense_rows(
	expenses: Iterable[Expense],
) -> tuple[tuple[str, str, str, str, str], ...]:
	return tuple(
		(
			expense.id,
			expense.date.isoformat(),
			ExpenseCategory.from_value(expense.category).value,
			format(expense.amount, ".2f"),
			expense.description,
		)
		for expense in expenses
	)


@st.cache_data(show_spinner=False)
def _expenses_to_dataframe(
	rows: tuple[tuple[str, str, str, str, str], ...],
) -> pd.DataFrame:
	return pd.DataFrame.from_records(
		rows, columns=("ID", "Date", "Category", "Amount", "Description")
	)


def render_expense_table(
	manager: ExpenseManager, expenses: list[Expense]
) -> None:
	st.subheader("Expenses")
	rows = _expense_rows(expenses)
	visible_ids = [row[0] for row in rows]
	selected_id = st.session_state.get("table_selected_expense_id")
	if selected_id not in visible_ids:
		st.session_state.pop("table_selected_expense_id", None)
	if st.session_state.get("confirm_delete_id") not in visible_ids:
		st.session_state.pop("confirm_delete_id", None)

	if not rows:
		st.info("No expenses match this date range.")
		return

	dataframe = _expenses_to_dataframe(rows)
	st.dataframe(
		dataframe.drop(columns=["ID"]),
		hide_index=True,
		width="stretch",
	)
	labels = {
		row[0]: f"{row[1]} · {row[2]} · {row[3]} · {row[4] or 'No description'}"
		for row in rows
	}
	selected_id = st.selectbox(
		"Select an expense to manage",
		options=visible_ids,
		index=None,
		placeholder="Choose an expense",
		format_func=labels.__getitem__,
		key="table_selected_expense_id",
	)
	if selected_id:
		edit_column, delete_column = st.columns(2)
		if edit_column.button("Edit selected", key=f"edit_{selected_id}"):
			st.session_state["editing_expense_id"] = selected_id
			st.session_state.pop("confirm_delete_id", None)
			st.rerun()
		if delete_column.button("Delete selected", key=f"delete_{selected_id}"):
			st.session_state["confirm_delete_id"] = selected_id
			st.session_state.pop("editing_expense_id", None)
			st.rerun()

	confirm_delete_id = st.session_state.get("confirm_delete_id")
	if confirm_delete_id:
		pending_expense = manager.get_expense(confirm_delete_id)
		if pending_expense is not None:
			st.warning(
				f"Delete {pending_expense.category.value} expense of "
				f"{pending_expense.amount:.2f} from {pending_expense.date.isoformat()}?"
			)
			confirm_column, cancel_column = st.columns(2)
			if confirm_column.button(
				"Confirm delete", key=f"confirm_delete_{confirm_delete_id}"
			):
				manager.delete_expense(confirm_delete_id)
				st.session_state.pop("confirm_delete_id", None)
				st.toast("Expense deleted.")
				st.rerun()
			if cancel_column.button(
				"Keep expense", key=f"cancel_delete_{confirm_delete_id}"
			):
				st.session_state.pop("confirm_delete_id", None)
				st.rerun()


def render_analytics_dashboard(
	manager: ExpenseManager, expenses: list[Expense]
) -> None:
	st.subheader("Spending overview")
	total_spending = manager.get_total_spending(expenses)
	category_totals = manager.get_category_totals(expenses)
	st.metric("Total spending", format(total_spending, ".2f"))

	chart_totals = [
		(category.value, total)
		for category, total in category_totals.items()
		if total > 0
	]
	if chart_totals:
		st.bar_chart(
			{
				"Category": [category for category, _ in chart_totals],
				"Amount": [float(total) for _, total in chart_totals],
			},
			x="Category",
			y="Amount",
		)
	else:
		st.caption("Add an expense to see the category breakdown.")


def main() -> None:
	st.set_page_config(page_title="FinanzApp", layout="wide")
	st.title("FinanzApp")
	manager = ExpenseSession.get_manager()
	render_expense_form(manager)
	start_date, end_date = render_sidebar_filters(manager)
	try:
		filtered_expenses = manager.filter_expenses(start_date, end_date)
	except ValueError as error:
		st.error(str(error))
		filtered_expenses = []

	st.divider()
	render_analytics_dashboard(manager, filtered_expenses)
	st.divider()
	render_expense_table(manager, filtered_expenses)

	editing_expense_id = st.session_state.get("editing_expense_id")
	if editing_expense_id:
		_render_edit_form(manager, editing_expense_id)


if __name__ == "__main__":
	main()
