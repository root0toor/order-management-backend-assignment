class OrderNotFoundError(Exception):
    pass


class InvalidStatusTransitionError(Exception):
    pass


class CannotCancelOrderError(Exception):
    pass
