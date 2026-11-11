"""Domain errors. Messages are Persian because they are shown to customers and staff."""


class DomainError(Exception):
    code: str = "domain_error"
    status_code: int = 422
    support_offer: bool = False

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ConfigurationError(DomainError):
    code = "configuration"
    status_code = 500


class NotFoundError(DomainError):
    code = "not_found"
    status_code = 404


class InvalidPhoneError(DomainError):
    code = "invalid_phone"


class TimeRuleError(DomainError):
    code = "time_rule"


class DesignLeadTimeError(DomainError):
    code = "design_lead_time"
    support_offer = True


class PricingError(DomainError):
    code = "pricing"


class InvalidTransitionError(DomainError):
    code = "invalid_transition"
    status_code = 409


class PaymentStateError(DomainError):
    code = "payment_state"
    status_code = 409


class TableConflictError(DomainError):
    code = "table_conflict"
    status_code = 409


class CapacityNotConfiguredError(DomainError):
    code = "capacity_not_configured"
    status_code = 409


class CancellationRequiresSupportError(DomainError):
    code = "cancellation_requires_support"
    support_offer = True


class PermissionDeniedError(DomainError):
    code = "permission_denied"
    status_code = 403


class SettingsVersionConflictError(DomainError):
    code = "settings_conflict"
    status_code = 409


class NoActiveTicketError(DomainError):
    code = "no_active_ticket"
    status_code = 409
