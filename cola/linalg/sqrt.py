from plum import dispatch
from cola.fns import lazify
from cola.annotations import SelfAdjoint
from cola.ops import Diagonal
from cola.ops import Kronecker
from cola.ops import LinearOperator
from cola.utils import export


@dispatch
@export
def sqrt(A: LinearOperator):
    """ Matrix sqrt of a Linear operator. If S=Sqrt(A), then S@S = A."""
    if A.isa(SelfAdjoint):
        xnp = A.ops
        eig_vals, eig_vecs = xnp.eigh(A.to_dense())
        Lambda = Diagonal(xnp.sqrt(eig_vals))
        Q = lazify(eig_vecs)
        return SelfAdjoint(Q @ Lambda @ Q.T)
    else:
        raise NotImplementedError(f"sqrt not implemented for {type(A)}")


@dispatch
def sqrt(A: Diagonal) -> Diagonal:
    xnp = A.ops
    return Diagonal(xnp.sqrt(A.diag))


@dispatch
def sqrt(A: Kronecker) -> Kronecker:
    Ms = [sqrt(Mi) for Mi in A.Ms]
    return Kronecker(*Ms)
