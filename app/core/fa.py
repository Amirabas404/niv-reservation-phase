"""Persian display helpers shared by the Backend, worker and bots."""

_FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def fa(value: object) -> str:
    return str(value).translate(_FA)


def money(amount: int | None) -> str:
    if amount is None:
        return "—"
    return f"{fa(f'{amount:,}')} تومان"
