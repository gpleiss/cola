from typing import Callable
from cola.ops import LinearOperator
from cola.algorithms.lanczos import lanczos_parts
from cola.algorithms.lanczos import construct_tridiagonal_batched
from cola.algorithms.cg import cg
from cola.utils import export
from cola.utils.custom_autodiff import iterative_autograd


@export
def stochastic_lanczos_quad(A: LinearOperator, fun: Callable, num_samples: int, max_iters: int,
                            tol: float = 1e-7, pbar: bool = False):
    """Approximates trace(f(A)) for a positive definite operator A.

    Args:
        A (LinearOperator): The linear operator representing the matrix A.
        fun (Callable): The function to apply to the eigenvalues.
        num_samples (int): The number of samples to use for the approximation.
        max_iters (int): The maximum number of iterations to run Lanczos.
        tol (float, optional): The tolerance criteria to stop Lanczos. Defaults to 1e-7.
        pbar (bool, optional): flag to print progress bar

    Returns:
        float: The approximate value of trace(f(A)).
    """
    # TODO: how can we jit here given the iter shape change?
    xnp = A.ops
    rhs = xnp.randn(A.shape[1], num_samples, dtype=A.dtype)
    alpha, beta, _, iters, _ = lanczos_parts(A, rhs, max_iters, tol, pbar)
    alpha, beta = alpha[..., :iters - 1], beta[..., :iters]
    T = construct_tridiagonal_batched(alpha, beta, alpha)
    eigvals, Q = xnp.eigh(T)
    tau = Q[..., 0, :]
    approx = xnp.sum(tau**2 * fun(eigvals), axis=-1)
    estimate = A.shape[-2] * approx
    return xnp.mean(estimate, axis=0)


def slq_bwd(res, grads, unflatten, *args, **kwargs):
    op_args, *_ = res
    num_samples = kwargs["num_samples"]
    A = unflatten(op_args)
    xnp = A.ops
    probes = xnp.randn(A.shape[1], num_samples, dtype=A.dtype)
    probes_solves, _ = cg(A, probes, tol=1e-6, max_iters=100)

    coef = 1.0 / probes.shape[-1]
    d_solves = coef * grads[0] * probes_solves

    def fun(*theta):
        Aop = unflatten(theta)
        return Aop @ probes

    d_params = xnp.vjp_derivs(fun=fun, primals=op_args, duals=d_solves)
    dA = unflatten(d_params)
    return (dA, )


@iterative_autograd(slq_bwd)
def slq_fwd(A, fun, num_samples, max_iters, tol, pbar):
    return stochastic_lanczos_quad(A, fun, num_samples, max_iters, tol, pbar)
