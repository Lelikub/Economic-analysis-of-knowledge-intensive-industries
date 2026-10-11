import math

import numpy as np
import pytest

from catalyst_risk_pipeline.analytics import (
    cvar, frechet_bounds, joint_failure_probability, parallel_reliability,
    series_reliability, tco_annual, annual_loss,
)
from catalyst_risk_pipeline.simulation import simulate_independent, simulate_pair, calibrate_latent
from catalyst_risk_pipeline.loaders import InputDataLoader, ALIASES
from catalyst_risk_pipeline.validators import DataValidator


def test_series_extremes():
    assert series_reliability([1, 1, 1, 1, 1]) == 1
    assert series_reliability([1, 1, 0, 1, 1]) == 0
    assert annual_loss(0, 8, 4, 0) == 0


def test_parallel_independent_and_extremes():
    assert parallel_reliability(.92, .9, 0) == pytest.approx(.992)
    assert parallel_reliability(0, 0, 0) == 0
    assert parallel_reliability(1, .9, 0) == 1


def test_frechet_and_positive_dependence():
    lo, hi = frechet_bounds(.92, .9)
    assert lo < 0 < .2 < hi
    assert parallel_reliability(.92, .9, .2) < parallel_reliability(.92, .9, 0)
    with pytest.raises(ValueError):
        joint_failure_probability(.92, .9, hi + .01)
    p00 = joint_failure_probability(.92, .9, .2)
    p01 = .08 - p00
    p10 = .1 - p00
    p11 = 1 - p00 - p01 - p10
    assert min(p00, p01, p10, p11) >= 0
    assert sum([p00, p01, p10, p11]) == pytest.approx(1)


def test_tco_and_cvar_tie_at_var():
    assert tco_annual(6, .3333, .4, .6) == pytest.approx(2.9998)
    losses = np.array([0] * 95 + [10] * 4 + [100], dtype=float)
    assert cvar(losses, .95) == pytest.approx(28)
    assert cvar(losses, .99) == pytest.approx(100)


def test_independent_simulation_reproducible():
    r = [1, .92, .98, .96, .94]
    a = simulate_independent(r, 500, 17, 2.0794, .55, 8, 4)
    b = simulate_independent(r, 500, 17, 2.0794, .55, 8, 4)
    np.testing.assert_array_equal(a['loss'], b['loss'])
    assert len(a['loss']) == 500
    assert np.all(a['loss'] >= 0)
    assert np.all(a['downtime'] >= 0)


def test_loader_normalizes_both_matrix_axes():
    data = InputDataLoader().load('../data')
    assert len(data.nodes) == 6
    assert len(data.incidents) == 50
    assert data.base_matrix.names[1] == ALIASES['Node_2_HF_Main']
    assert data.base_matrix.names[4] == ALIASES['Node_4_Nitrogen']
    assert data.base_matrix.values.shape == (6, 6)


def test_supplied_matrices_and_pair_calibration():
    data = InputDataLoader().load('../data')
    issues = DataValidator().validate(data)
    assert not [x for x in issues if x['severity'] == 'BLOCKER']
    r = [data.nodes[k].reliability for k in data.base_matrix.names]
    latent, diagnostics = calibrate_latent(data.base_matrix.values, r)
    assert np.linalg.eigvalsh(latent).min() >= -1e-8
    assert diagnostics['max_joint_residual'] < 1e-7


def test_pair_simulation_tracks_analytic_reliability():
    r = [.95, .92, .98, .96, .94]
    sample = simulate_pair(r, .9, .2, 10_000, 19, 2.0794, .55, 8, 4)
    expected = series_reliability([r[0], parallel_reliability(.92, .9, .2), *r[2:]])
    assert abs(sample['ok'].mean() - expected) < .02


def test_dual_simulation_preserves_main_and_backup_states():
    sample = simulate_independent([1, 0, 1, 1, 1], 10, 4, 2, .5, 8, 4, backup=1)
    assert sample['states'].shape == (10, 6)
    assert not sample['states'][:, 1].any()
    assert sample['states'][:, 2].all()
    assert sample['ok'].all()
