# Naplózási konfiguráció – strukturált logging az egész alkalmazáshoz
import logging
import sys


def get_logger(name: str) -> logging.Logger:
    """
    Névvel ellátott logger létrehozása egységes formátummal.
    A naplóbejegyzések tartalmazzák az időbélyeget, szintet és modult.

    Args:
        name: A logger neve (általában __name__ az adott modulban)

    Returns:
        logging.Logger: Konfigurált logger példány
    """
    logger = logging.getLogger(name)

    # Ne adjunk hozzá ismételt handler-t, ha már konfigurálva van
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Konzolra írás (stdout) – Cloud Run és lokális fejlesztéshez egyaránt
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)

    # Naplóbejegyzés formátuma
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
