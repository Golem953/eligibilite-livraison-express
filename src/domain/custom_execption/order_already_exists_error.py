class OrderAlreadyExistsError(ValueError):
    """Une commande porte déjà cet identifiant."""

    def __init__(self, order_id: str) -> None:
        super().__init__(f"La commande {order_id} existe déjà.")
        self.order_id = order_id
