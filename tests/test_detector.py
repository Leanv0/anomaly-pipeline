"""
test_detector.py — Pruebas unitarias para las funciones de detección y métricas de seguridad.

Valida las reglas heurísticas, preparación de matrices de features y cálculo
de métricas de ciberseguridad (Matriz de confusión, Precisión, Recall, FPR)
de manera aislada sin requerir servicios externos.
"""

import sys
from pathlib import Path
import pytest
import numpy as np
import pandas as pd

# Agregamos src/ al PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from detector import (
    prepare_features_and_labels,
    detect_rules,
    evaluate_detector,
    train_isolation_forest,
    predict_isolation_forest,
    CONSTANT_COLUMNS,
)


def test_prepare_features_and_labels_binary_mapping(sample_clean_traffic_df):
    """
    Verifica que prepare_features_and_labels:
    1. Mapee 'BENIGN' a 0 y cualquier ataque ('PortScan') a 1.
    2. Separe la etiqueta 'Label' fuera de la matriz X.
    3. Remueva las columnas constantes conocidas (ej: 'Bwd PSH Flags').
    """
    X, y = prepare_features_and_labels(sample_clean_traffic_df, drop_constants=True)

    # 1. Verificar vector y
    assert list(y) == [0, 1, 0, 1, 0]

    # 2. Verificar matriz X
    assert "Label" not in X.columns
    assert "Bwd PSH Flags" not in X.columns
    assert len(X) == len(sample_clean_traffic_df)


def test_detect_rules_signature_accuracy(sample_clean_traffic_df):
    """
    Verifica que la regla de firma TCP identifique con precisión quirúrgica
    los flujos de escaneo de puertos (PSH=1, ACK=0, duración corta, pocos paquetes)
    y no genere falsos positivos en los flujos benignos.
    """
    X, y = prepare_features_and_labels(sample_clean_traffic_df)
    preds = detect_rules(X, strategy="signature")

    # En sample_clean_traffic_df las filas en índice 1 y 3 son PortScan con flags PSH=1, ACK=0
    assert list(preds) == [0, 1, 0, 1, 0]


def test_detect_rules_invalid_strategy(sample_clean_traffic_df):
    """
    Verifica que la función lance ValueError si se especifica una estrategia no soportada.
    """
    X, _ = prepare_features_and_labels(sample_clean_traffic_df)
    with pytest.raises(ValueError, match="Estrategia desconocida"):
        detect_rules(X, strategy="estrategia_inexistente")


def test_evaluate_detector_metrics():
    """
    Verifica el cálculo matemático de las métricas clave de un SOC:
    - TP, FP, FN, TN
    - Precisión = TP / (TP + FP)
    - Recall = TP / (TP + FN)
    - FPR = FP / (FP + TN)
    """
    # 2 ataques reales (índices 0, 1) y 2 normales (índices 2, 3)
    y_true = pd.Series([1, 1, 0, 0])
    # Detector acierta el primer ataque, no ve el segundo (FN), y confunde un normal (FP)
    y_pred = pd.Series([1, 0, 1, 0])

    metrics = evaluate_detector(y_true, y_pred, detector_name="TestUnitario")

    assert metrics["true_positives"] == 1
    assert metrics["false_negatives"] == 1
    assert metrics["false_positives"] == 1
    assert metrics["true_negatives"] == 1

    # Precision: 1 / (1 + 1) = 0.5
    assert metrics["precision"] == 0.5
    # Recall: 1 / (1 + 1) = 0.5
    assert metrics["recall"] == 0.5
    # FPR: 1 / (1 + 1) = 0.5
    assert metrics["fpr"] == 0.5


def test_isolation_forest_training_and_prediction(sample_clean_traffic_df):
    """
    Prueba unitaria de entrenamiento y predicción de Isolation Forest
    con datos sintéticos para validar que complete el ciclo y devuelva tipos válidos.
    """
    X, _ = prepare_features_and_labels(sample_clean_traffic_df)

    # Entrenar un bosque pequeño para prueba rápida
    model, features_usadas = train_isolation_forest(
        X_train=X,
        n_estimators=10,
        max_samples=len(X),
        random_state=42,
    )

    preds, scores = predict_isolation_forest(model, X, features=features_usadas)

    # Las predicciones deben ser binarias (0 o 1)
    assert set(preds.unique()).issubset({0, 1})
    # Los scores deben ser floats con la misma cantidad de elementos
    assert len(scores) == len(X)
    assert isinstance(scores, np.ndarray)


def test_main_module_importable():
    """
    Smoke test para asegurar que el orquestador principal src/main.py
    se importe correctamente sin lanzar excepciones de sintaxis ni de dependencias.
    """
    import main
    assert hasattr(main, "main")
    assert hasattr(main, "parse_arguments")
