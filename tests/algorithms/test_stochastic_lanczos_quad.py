from cola import jax_fns
import numpy as np
from cola import torch_fns
from cola.algorithms.stochastic_lanczos_quad import stochastic_lanczos_quad
from cola.basic_operations import lazify
from cola.utils_test import parametrize, relative_error
from cola.utils_test import generate_spectrum, generate_pd_from_diag
from jax.config import config
config.update('jax_platform_name', 'cpu')


@parametrize([torch_fns, jax_fns])
def test_stochastic_lanczos_quad_random(xnp):
    dtype = xnp.float32
    diag = generate_spectrum(coeff=0.5, scale=1.0, size=10, dtype=np.float32)
    A = xnp.array(generate_pd_from_diag(diag, dtype=diag.dtype), dtype=dtype)

    def fun(x):
        return xnp.log(x)

    soln = xnp.sum(fun(xnp.array(diag, dtype=dtype)))
    num_samples, max_iters, tol = 70, A.shape[0], 1e-7
    approx = stochastic_lanczos_quad(lazify(A), fun, num_samples, max_iters, tol)

    rel_error = relative_error(soln, approx)
    assert rel_error < 1e-1
