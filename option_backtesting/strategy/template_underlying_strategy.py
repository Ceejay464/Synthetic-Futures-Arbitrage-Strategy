class TemplateUnderlyingStrategy:

    def __init__(self):

        self.has_bought = False

    def generate_signal(self, timestamp, underlying_snapshot, option_snapshot, portfolio, option_db):

        date = timestamp
        orders = []
        return orders