"""
Importamos todos los modelos acá para poder escribir, por ejemplo:
    from backend.app.models import User, Expense
y para que SQLModel conozca todas las tablas al crearlas.
"""

from .commission import Commission, CommissionCreate, CommissionRead, CommissionUpdate
from .common import Currency
from .exchange_rate import ExchangeRate
from .expense import (
    Expense, ExpenseCategory, ExpenseCreate, ExpenseKind, ExpenseRead, ExpenseUpdate,
)
from .goal import Goal, GoalCreate, GoalRead, GoalUpdate
from .pay_record import PayKind, PayRecord, PayRecordCreate, PayRecordRead, PayRecordUpdate
from .income import Income, IncomeCreate, IncomeFrequency, IncomeRead, IncomeUpdate
from .subscription import (
    Subscription, SubscriptionCreate, SubscriptionFrequency, SubscriptionRead,
    SubscriptionUpdate,
)
from .support import Feedback, FeedbackCreate, PasswordReset
from .user import PasswordChange, PasswordResetIn, Token, User, UserCreate, UserRead, UserUpdate
from .wish import Priority, WishItem, WishItemCreate, WishItemRead, WishItemUpdate
