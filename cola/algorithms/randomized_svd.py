from cola.utils import export

@export
def randomized_svd(A, rank):
    """ TODO Andres: make docstring"""
    xnp = A.ops
    Omega = xnp.randn(*(A.shape[0], rank), dtype=A.dtype)
    Y = A @ Omega
    Q, _ = xnp.qr(Y, full_matrices=False)
    B = Q.T @ A
    U, Sigma, V = xnp.svd(B, full_matrices=False)
    return Sigma, Q @ U, V
