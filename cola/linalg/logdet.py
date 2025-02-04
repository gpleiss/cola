from plum import dispatch
from cola.ops import Array
from cola.ops import LinearOperator
from cola.ops import Diagonal, Kronecker, BlockDiag
from cola.utils import export

@dispatch
@export
def logdet(A: LinearOperator, tol=1e-7, info=False, pbar=True) -> Array:
    # add casework
    raise NotImplementedError


@dispatch
def logdet(A: Diagonal, **kwargs) -> Array:
    xnp = A.ops
    out = xnp.sum(xnp.log(A.diag))
    return out


@dispatch
def logdet(A: Kronecker, **kwargs) -> Array:
    # logdet(Pi A_i \otimes I) = sum_i logdet(A_i)
    return sum(logdet(A.Ai) for Ai in A.Ms)


@dispatch
def logdet(A: BlockDiag, **kwargs) -> Array:
    # logdet(\bigoplus A_i) = log \prod det(A_i) = sum_i logdet(A_i)
    return sum(logdet(A.Ai) for Ai in A.Ms)
