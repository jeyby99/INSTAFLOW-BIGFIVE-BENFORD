"""
InstaFlow Benford Analysis
==========================
Implementación pura (sin dependencias de Selenium/Flask) de la Ley de
Benford aplicada al primer dígito significativo de una lista de contadores
(p. ej., el `followers_count` de cada persona en un listado de seguidores
o seguidos).

Flujo:
  1) Para cada valor, se obtiene su primer dígito significativo (1-9).
  2) Se compara la distribución observada contra la distribución teórica
     de Benford: P(d) = log10(1 + 1/d).
  3) Se calcula el estadístico chi-cuadrado de bondad de ajuste
     (grados de libertad = 8, por los 9 dígitos posibles).
  4) Se clasifica el resultado en "humano", "posible_bot" o "bot" según
     umbrales de chi-cuadrado configurables (valores críticos estándar
     para df=8: 15.51 → p=0.05, 20.09 → p=0.01).

Este módulo no sabe nada de Instagram, Selenium ni Flask: solo recibe una
lista de números. Esto lo hace fácil de probar de forma aislada
(ver tests/test_benford_analysis.py).
"""

import math

# Dígitos significativos posibles (el primer dígito nunca puede ser 0).
BENFORD_DIGITS: list[int] = list(range(1, 10))

# Umbrales por defecto si el llamador no especifica otros (deben coincidir
# con config.BENFORD_CHI2_BOT_THRESHOLD / BENFORD_CHI2_POSSIBLE_BOT_THRESHOLD).
DEFAULT_BOT_THRESHOLD: float = 20.09
DEFAULT_POSSIBLE_BOT_THRESHOLD: float = 15.51
DEFAULT_MIN_SAMPLE_SIZE: int = 10


def first_significant_digit(value) -> int | None:
    """
    Retorna el primer dígito significativo (1-9) de un número.

    Reglas:
    - None, valores no numéricos, negativos o cero -> None (se excluyen
      del análisis; NO se fuerzan a 0 ni se inventan).
    - Acepta int, float o str numérica.
    """
    if value is None:
        return None
    try:
        # Admitir floats truncando a entero (ej. 1500.0 -> 1500)
        n = int(float(value))
    except (TypeError, ValueError):
        return None

    if n <= 0:
        return None

    while n >= 10:
        n //= 10

    return n if 1 <= n <= 9 else None


def benford_expected_proportions() -> dict[int, float]:
    """Distribución teórica de Benford: P(d) = log10(1 + 1/d) para d en 1..9."""
    return {d: math.log10(1 + 1 / d) for d in BENFORD_DIGITS}


def compute_benford_analysis(
    values: list,
    min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE,
    bot_threshold: float = DEFAULT_BOT_THRESHOLD,
    possible_bot_threshold: float = DEFAULT_POSSIBLE_BOT_THRESHOLD,
) -> dict:
    """
    Calcula la distribución del primer dígito, el chi-cuadrado de bondad
    de ajuste contra la Ley de Benford, y clasifica el resultado.

    Retorna un diccionario listo para persistir en JSON y para graficar
    en el dashboard (curva teórica vs. observada).
    """
    expected_props = benford_expected_proportions()

    digits = [first_significant_digit(v) for v in values]
    valid_digits = [d for d in digits if d is not None]
    n = len(valid_digits)

    observed_counts = {d: 0 for d in BENFORD_DIGITS}
    for d in valid_digits:
        observed_counts[d] += 1

    result: dict = {
        "sample_size": n,
        "total_values_received": len(values),
        "excluded_count": len(values) - n,
        "digits": BENFORD_DIGITS,
        "observed_counts": [observed_counts[d] for d in BENFORD_DIGITS],
        "observed_proportions": [0.0 for _ in BENFORD_DIGITS],
        "expected_proportions": [round(expected_props[d], 6) for d in BENFORD_DIGITS],
        "expected_counts": [0.0 for _ in BENFORD_DIGITS],
        "chi_square": None,
        "degrees_of_freedom": len(BENFORD_DIGITS) - 1,
        "bot_threshold": bot_threshold,
        "possible_bot_threshold": possible_bot_threshold,
        "classification": "sin_datos_suficientes",
        "classification_label": "Sin datos suficientes",
        "verdict_message": (
            "No se obtuvo ningún contador de seguidores válido para analizar."
        ),
    }

    if n == 0:
        return result

    result["observed_proportions"] = [round(observed_counts[d] / n, 6) for d in BENFORD_DIGITS]
    expected_counts = [expected_props[d] * n for d in BENFORD_DIGITS]
    result["expected_counts"] = [round(c, 4) for c in expected_counts]

    chi_square = sum(
        ((observed_counts[d] - expected_counts[i]) ** 2) / expected_counts[i]
        for i, d in enumerate(BENFORD_DIGITS)
        if expected_counts[i] > 0
    )
    chi_square = round(chi_square, 4)
    result["chi_square"] = chi_square

    if n < min_sample_size:
        result["classification"] = "sin_datos_suficientes"
        result["classification_label"] = "Muestra insuficiente"
        result["verdict_message"] = (
            f"Solo se obtuvieron {n} contadores válidos (mínimo recomendado: "
            f"{min_sample_size}). χ²={chi_square}, pero el resultado no es "
            "estadísticamente confiable con una muestra tan pequeña."
        )
    elif chi_square > bot_threshold:
        result["classification"] = "bot"
        result["classification_label"] = "Bot"
        result["verdict_message"] = (
            f"χ²={chi_square} supera el umbral de {bot_threshold} (p<0.01): "
            "la distribución de primeros dígitos se aleja fuertemente de la "
            "Ley de Benford, un indicio típico de cuentas automatizadas/bots."
        )
    elif chi_square > possible_bot_threshold:
        result["classification"] = "posible_bot"
        result["classification_label"] = "Posible Bot"
        result["verdict_message"] = (
            f"χ²={chi_square} está entre {possible_bot_threshold} y {bot_threshold} "
            "(p entre 0.01 y 0.05): hay una desviación moderada de Benford, "
            "no concluyente por sí sola."
        )
    else:
        result["classification"] = "humano"
        result["classification_label"] = "Humano"
        result["verdict_message"] = (
            f"χ²={chi_square} no supera {possible_bot_threshold} (p>0.05): la "
            "distribución observada es compatible con la Ley de Benford, "
            "consistente con una red de seguidores orgánica."
        )

    return result
