from cola import jax_fns
from cola import torch_fns
from cola.fns import lazify
from cola.algorithms.preconditioners import get_nys_approx
from cola.algorithms.preconditioners import select_rank_adaptively
from cola.algorithms.preconditioners import NystromPrecond
from cola.algorithms.preconditioners import AdaNysPrecond
from cola.algorithms.preconditioners import sqrt
from cola.algorithms.preconditioners import inverse
from cola.utils_test import parametrize, relative_error, construct_e_vec
from cola.utils_test import generate_spectrum, generate_pd_from_diag
from jax.config import config

config.update('jax_platform_name', 'cpu')
# config.update("jax_enable_x64", True)

_tol = 1e-7


@parametrize([torch_fns, jax_fns])
def test_AdaNysPrecond(xnp):
    dtype = xnp.float32
    diag = generate_spectrum(coeff=0.5, scale=1.0, size=16)
    A = xnp.array(generate_pd_from_diag(diag, dtype=diag.dtype, seed=21), dtype=dtype)
    B = lazify(A)

    rank_init, bounds, mult = 2, (0.2, 0.4, 0.6), 1.5  # first case
    Nys = AdaNysPrecond(A=B, rank=rank_init, mult=mult, bounds=bounds, adjust_mu=False)
    approx = Nys.error

    assert approx < bounds[-1]

    rank_init, bounds, mult = 2, (0.05, 0.9, 0.95), 1.5  # middle case
    Nys = AdaNysPrecond(A=B, rank=rank_init, mult=mult, bounds=bounds, adjust_mu=False)

    rank_init, bounds, mult = A.shape[0], (0.1, 0.2, 0.8), 1.5  # last case
    Nys = AdaNysPrecond(A=B, rank=rank_init, mult=mult, bounds=bounds, adjust_mu=False)
    approx = Nys.rank
    ones = xnp.ones((Nys.shape[0], 1), dtype=dtype)
    ones_approx = (Nys @ A @ ones) * (1. / Nys.preconditioned_eigmax)

    rel_error = relative_error(ones, ones_approx)
    assert rel_error < 1e-4
    assert approx == round(rank_init / mult)


@parametrize([torch_fns, jax_fns])
def test_select_rank_adaptively(xnp):
    dtype = xnp.float32
    diag = generate_spectrum(coeff=0.5, scale=1.0, size=16)
    A = soln = xnp.array(generate_pd_from_diag(diag, dtype=diag.dtype), dtype=dtype)
    rank_init, rank_max, tol = 4, 20, 1e-5

    B = lazify(A)
    Lambda, U, _ = select_rank_adaptively(B, rank_init, rank_max, tol, mult=1.5)
    approx = U @ (xnp.diag(Lambda)) @ U.T

    rel_error = relative_error(soln, approx)
    print(f"\nRel error: {rel_error:1.3e}")
    assert rel_error < 5e-5


@parametrize([torch_fns, jax_fns])
def test_nys_sqrt_inverse(xnp):
    dtype = xnp.float32
    diag = generate_spectrum(coeff=0.5, scale=1.0, size=10)
    A = xnp.array(generate_pd_from_diag(diag, dtype=diag.dtype, seed=21), dtype=dtype)
    rank = A.shape[0] // 2

    Nys = NystromPrecond(lazify(A), rank=rank)

    approx = sqrt(Nys).to_dense()
    rel_error = relative_error(Nys.to_dense(), approx @ approx)
    assert rel_error < _tol * 10

    approx = inverse(Nys).to_dense()
    rel_error = relative_error(xnp.eye(Nys.shape[0]), approx @ Nys.to_dense())
    assert rel_error < _tol * 10

    approx = inverse(sqrt(inverse(sqrt(Nys)))).to_dense()
    rel_error = relative_error(Nys.to_dense(), approx @ approx @ approx @ approx)
    assert rel_error < _tol * 10


@parametrize([torch_fns, jax_fns])
def test_nys_precond(xnp):
    dtype = xnp.float32
    diag = generate_spectrum(coeff=0.5, scale=1.0, size=10)
    A = xnp.diag(xnp.array(diag, dtype=dtype))
    basis = [
        xnp.array(construct_e_vec(i=i, size=A.shape[0]), dtype=dtype)[:, None]
        for i in range(A.shape[0])
    ]
    mu = 1e-8
    rank = A.shape[0] // 2
    Omega = xnp.concat(basis[:rank], axis=1)
    Omega2 = xnp.concat(basis[rank:], axis=1)

    B = lazify(A)
    Nys = NystromPrecond(B, rank=rank)
    Nys._create_approx(B, xnp.copy(Omega), mu=mu, eps=1e-8, adjust_mu=False)

    P = Nys @ xnp.eye(B.shape[0])
    Psqrt = P**0.5
    approx = Psqrt @ A @ Psqrt

    subspace = xnp.diag(xnp.array(1 / (diag[:rank] + mu), dtype=dtype))
    soln_P = diag[rank - 1] * Omega @ subspace @ Omega.T
    soln_P += xnp.eye(Omega.shape[0]) - Omega @ Omega.T

    inv = (A + mu * xnp.eye(B.shape[0]))[rank:, rank:]
    soln = (diag[rank - 1] + mu) * Omega @ Omega.T + Omega2 @ (inv @ Omega2.T)
    rel_error = relative_error(soln, approx)
    assert rel_error < _tol * 10
    rel_error = relative_error(soln_P, P)
    assert rel_error < _tol * 10


@parametrize([torch_fns, jax_fns])
def test_get_nys_approx_random(xnp):
    dtype = xnp.float32
    diag = generate_spectrum(coeff=0.5, scale=1.0, size=10)
    A = soln = xnp.array(generate_pd_from_diag(diag, dtype=diag.dtype), dtype=dtype)
    rank = A.shape[0]
    Omega = xnp.fixed_normal_samples(shape=(A.shape[0], rank), dtype=dtype)

    B = lazify(A)
    fn = xnp.jit(get_nys_approx, static_argnums=(0, 2))
    Lambda, U = fn(B, Omega, eps=1e-6)
    approx = U @ (Lambda[:, None] * U.T)

    rel_error = relative_error(soln, approx)
    print(f"\nRel error: {rel_error:1.3e}")
    assert rel_error < _tol * 500


@parametrize([torch_fns, jax_fns])
def test_get_nys_approx_diagonal(xnp):
    dtype = xnp.float32
    A = xnp.diag(xnp.array([3., 4., 5., 7., 1.], dtype=dtype))
    e1 = xnp.array(construct_e_vec(i=0, size=A.shape[0]), dtype=dtype)[:, None]
    e3 = xnp.array(construct_e_vec(i=2, size=A.shape[0]), dtype=dtype)[:, None]
    e5 = xnp.array(construct_e_vec(i=4, size=A.shape[0]), dtype=dtype)[:, None]
    Omega = xnp.concat((e1, e5, e3), axis=1)
    soln = xnp.diag(xnp.array([3., 0., 5., 0., 1.], dtype=dtype))

    B = lazify(A)
    fn = xnp.jit(get_nys_approx, static_argnums=(0, 2))
    Lambda, U = fn(B, Omega, eps=1e-6)
    approx = U @ (Lambda[:, None] * U.T)

    rel_error = relative_error(soln, approx)
    assert rel_error < _tol
    # rel_error = relative_error(Omega[:, [2, 0, 1]], U)
    # assert rel_error < _tol
