"""
Tests for scraper.benford_analysis
===================================
Pruebas unitarias puras (sin Selenium ni red) de la Ley de Benford:
primer dígito significativo, chi-cuadrado y clasificación Bot/Posible Bot/Humano.
"""

import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scraper.benford_analysis import (
    BENFORD_DIGITS,
    benford_expected_proportions,
    compute_benford_analysis,
    first_significant_digit,
)


class TestFirstSignificantDigit:
    def test_simple_cases(self):
        assert first_significant_digit(7) == 7
        assert first_significant_digit(42) == 4
        assert first_significant_digit(1234567) == 1
        assert first_significant_digit(950000) == 9

    def test_handles_strings_and_floats(self):
        assert first_significant_digit("123") == 1
        assert first_significant_digit(123.9) == 1

    def test_excludes_invalid_values(self):
        # Nunca se inventa un dígito para datos ausentes o inválidos.
        assert first_significant_digit(None) is None
        assert first_significant_digit(0) is None
        assert first_significant_digit(-50) is None
        assert first_significant_digit("no disponible") is None


class TestBenfordExpectedProportions:
    def test_sums_to_one_and_decreasing(self):
        props = benford_expected_proportions()
        assert set(props.keys()) == set(BENFORD_DIGITS)
        assert math.isclose(sum(props.values()), 1.0, abs_tol=1e-9)
        # La Ley de Benford predice que el dígito 1 es el más frecuente
        # y la frecuencia decrece monótonamente hasta el 9.
        values = [props[d] for d in BENFORD_DIGITS]
        assert values == sorted(values, reverse=True)
        assert props[1] > 0.30  # ~30.1%
        assert props[9] < 0.05  # ~4.6%


class TestComputeBenfordAnalysis:
    def test_empty_or_all_invalid_values(self):
        result = compute_benford_analysis([])
        assert result["sample_size"] == 0
        assert result["classification"] == "sin_datos_suficientes"
        assert result["chi_square"] is None

        result2 = compute_benford_analysis([None, None, -5, 0])
        assert result2["sample_size"] == 0
        assert result2["classification"] == "sin_datos_suficientes"

    def test_small_sample_is_inconclusive(self):
        result = compute_benford_analysis([123, 456, 789], min_sample_size=10)
        assert result["sample_size"] == 3
        assert result["classification"] == "sin_datos_suficientes"
        # El chi-cuadrado sí se calcula, solo que se marca como no confiable.
        assert result["chi_square"] is not None

    def test_benford_like_distribution_classifies_as_human(self):
        # Generar valores log-uniformes: su primer dígito sigue la Ley de
        # Benford casi a la perfección (es la construcción canónica).
        random.seed(7)
        values = [int(10 ** random.uniform(1, 7)) for _ in range(3000)]
        result = compute_benford_analysis(values)
        assert result["sample_size"] == 3000
        assert result["classification"] == "humano"
        assert result["chi_square"] <= result["possible_bot_threshold"]

    def test_single_repeated_digit_classifies_as_bot(self):
        # Un listado donde todos los contadores empiezan con el mismo dígito
        # es la desviación más extrema posible de Benford -> debe ser "bot".
        values = [9000 + i for i in range(300)]
        result = compute_benford_analysis(values)
        assert result["sample_size"] == 300
        assert result["classification"] == "bot"
        assert result["chi_square"] > result["bot_threshold"]

    def test_classification_thresholds_are_respected(self):
        # Umbrales personalizados muy bajos deben forzar una clasificación
        # de "bot" incluso para una muestra razonablemente parecida a Benford.
        random.seed(1)
        values = [int(10 ** random.uniform(1, 6)) for _ in range(500)]
        strict_result = compute_benford_analysis(
            values, bot_threshold=0.01, possible_bot_threshold=0.005
        )
        assert strict_result["classification"] == "bot"

    def test_observed_proportions_sum_to_one(self):
        values = [111, 222, 333, 456, 789, 150, 275, 999, 101, 650, 310]
        result = compute_benford_analysis(values, min_sample_size=1)
        assert math.isclose(sum(result["observed_proportions"]), 1.0, abs_tol=1e-6)
        assert sum(result["observed_counts"]) == result["sample_size"]

    def test_excludes_invalid_but_keeps_valid(self):
        values = [150, None, -10, 0, "no disponible", 275]
        result = compute_benford_analysis(values, min_sample_size=1)
        assert result["sample_size"] == 2
        assert result["excluded_count"] == 4
        assert result["total_values_received"] == 6
