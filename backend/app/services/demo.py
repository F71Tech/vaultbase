"""
Cuenta demo: para que cualquiera (un reclutador, por ejemplo) pruebe la app
con un clic, sin registrarse.

Cada clic en "Probar la demo" crea una cuenta NUEVA con datos de ejemplo
realistas (de los últimos 10 meses, relativos a hoy). Así cada visitante
juega con su propia copia y nadie le rompe la demo a otro. Las demos viejas
se borran solas después de DEMO_TTL_HOURS horas.
"""

import datetime as dt
import random
import secrets

from sqlmodel import Session, select

from ..models import Expense, Goal, Income, Subscription, User, WishItem
from ..models.common import today_uy, utcnow
from ..security import hash_password
from .accounts import delete_user_data
from .finance import add_months, add_months_to_date, month_bounds
from .salary import SalaryInput, calculate

DEMO_DOMAIN = "demo.vaultbase.app"
DEMO_TTL_HOURS = 6
MONTHS_OF_HISTORY = 10


def is_demo_email(email: str) -> bool:
    return email.endswith("@" + DEMO_DOMAIN)


def cleanup_old_demos(session: Session) -> int:
    """Borra las cuentas demo creadas hace más de DEMO_TTL_HOURS horas."""
    limit = utcnow() - dt.timedelta(hours=DEMO_TTL_HOURS)
    old = session.exec(
        select(User).where(User.email.like(f"%@{DEMO_DOMAIN}"), User.created_at < limit)
    ).all()
    for user in old:
        delete_user_data(session, user.id)
    return len(old)


def _variable_expenses(rng: random.Random, user_id: int, today: dt.date) -> list[Expense]:
    """Gastos del día a día de los últimos meses, con montos que varían un poco."""
    items: list[Expense] = []

    def add(date, category, sub, low, high, description=None, currency="UYU", rate=None):
        if date <= today:  # nunca gastos "del futuro"
            items.append(Expense(
                user_id=user_id, category=category, subcategory=sub, kind="variable", date=date,
                amount_cents=rng.randint(low, high) * 100, description=description,
                currency=currency, exchange_rate=rate,
            ))

    for back in range(MONTHS_OF_HISTORY - 1, -1, -1):
        y, m = add_months(today.year, today.month, -back)
        first, last = month_bounds(y, m)
        day = lambda d: first + dt.timedelta(days=min(d, last.day) - 1)  # noqa: E731

        for week_day in (3, 10, 17, 24):
            add(day(week_day), "food", "groceries", 2100, 2900, "Compra del súper")
            add(day(week_day + 2), "food", "market", 400, 700, "Feria")
        for _ in range(rng.randint(1, 3)):
            add(day(rng.randint(1, 28)), "food", "delivery", 450, 780, "PedidosYa")
        for _ in range(rng.randint(4, 7)):
            add(day(rng.randint(1, 28)), "food", "snacks", 60, 190,
                rng.choice(["Alfajor", "Café", "Refresco", "Bizcochos"]))
        add(day(1), "transport", "bus", 1200, 1200, "Recarga STM")
        for _ in range(rng.randint(1, 3)):
            add(day(rng.randint(1, 28)), "transport", "taxi_apps", 260, 480, "Uber")
        for _ in range(rng.randint(1, 2)):
            add(day(rng.randint(5, 28)), "leisure", "outings", 800, 1600,
                rng.choice(["Salida con amigos", "Cine", "Cena", "Bar"]))
        add(day(rng.randint(1, 28)), "health", "pharmacy", 300, 800, "Farmacia")
        if rng.random() < 0.35:
            add(day(rng.randint(1, 28)), "clothing", "clothes", 1500, 3500, "Ropa")
        if rng.random() < 0.25:
            add(day(rng.randint(1, 28)), "gifts", "presents", 800, 2000, "Regalo de cumpleaños")
        if rng.random() < 0.2:
            add(day(rng.randint(1, 28)), "tech", "tech_accessories", 20, 45, "Accesorio para el celu",
                currency="USD", rate=round(rng.uniform(39.5, 40.5), 3))
    # Algo para "hoy", así la tarjeta "Hoy" del dashboard no aparece vacía
    add(today, "food", "snacks", 90, 90, "Alfajor y café")
    return items


def create_demo_user(session: Session) -> User:
    """Crea una cuenta demo nueva, llena de datos de ejemplo, y la devuelve."""
    cleanup_old_demos(session)
    today = today_uy()
    rng = random.Random()  # distinto cada vez, para que cada demo sea un poco diferente

    user = User(
        email=f"demo-{secrets.token_hex(4)}@{DEMO_DOMAIN}", name="Sofía",
        # Contraseña al azar que nadie conoce: a la demo solo se entra con el botón
        hashed_password=hash_password(secrets.token_urlsafe(24)), food_budget_pct=30,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    uid = user.id
    start = add_months_to_date(today, -MONTHS_OF_HISTORY).replace(day=1)

    # Sueldo calculado con la calculadora real (nominal $ 95.000)
    salary = calculate(SalaryInput(nominal_cents=9_500_000))
    rows = [
        Income(user_id=uid, source="Sueldo", amount_cents=salary.monthly.net_cents,
               nominal_cents=salary.monthly.nominal_cents, aguinaldo_cents=salary.aguinaldo.net_cents,
               start_date=start),
        Income(user_id=uid, source="Diseño freelance", amount_cents=900_000, frequency="one_time",
               start_date=add_months_to_date(today, -2)),
    ]
    fixed = [
        ("housing", "rent", 2_200_000, "Alquiler"), ("housing", "common_fees", 350_000, "Gastos comunes"),
        ("utilities", "electricity", 240_000, "UTE"), ("utilities", "water", 90_000, "OSE"),
        ("utilities", "internet_phone", 160_000, "Antel fibra + celular"),
    ]
    rows += [Expense(user_id=uid, category=c, subcategory=s, kind="fixed", amount_cents=a,
                     description=d, date=start) for c, s, a, d in fixed]
    rows += _variable_expenses(rng, uid, today)
    subs = [("Spotify", 1199, "USD", 10), ("Netflix", 1549, "USD", 18), ("Claude", 2000, "USD", 5),
            ("YouTube Premium", 1399, "USD", 22), ("Gimnasio", 180_000, "UYU", 1)]
    rows += [Subscription(user_id=uid, name=n, amount_cents=a, currency=c, billing_day=d,
                          created_at=dt.datetime.combine(start, dt.time(), tzinfo=dt.timezone.utc))
             for n, a, c, d in subs]
    rows += [
        Goal(user_id=uid, name="Viaje a Florianópolis", target_cents=4_500_000, saved_cents=1_250_000,
             deadline=add_months_to_date(today, 9)),
        Goal(user_id=uid, name="Fondo de emergencia", target_cents=12_000_000, saved_cents=5_400_000,
             monthly_contribution_cents=400_000),
        Goal(user_id=uid, name="Notebook nueva", target_cents=3_800_000, saved_cents=3_420_000),
    ]
    rows += [
        WishItem(user_id=uid, name="Auriculares con cancelación de ruido", cost_cents=19_900,
                 currency="USD", priority="high", notes="Esperar a una oferta"),
        WishItem(user_id=uid, name="Bicicleta", cost_cents=1_800_000, priority="medium"),
        WishItem(user_id=uid, name="Consola de videojuegos", cost_cents=59_900, currency="USD", priority="low"),
    ]
    session.add_all(rows)
    session.commit()
    return user
