import numpy as np
from plum import dispatch
from cola.ops import LinearOperator
from cola.ops import Diagonal, Permutation, Concatenated
from cola.ops import Identity
from cola.ops import ScalarMul
from cola.ops import BlockDiag
from cola.ops import Kronecker, Sum, Product
from cola.algorithms.cg import cg
from cola.algorithms.gmres import gmres
from cola.algorithms.svrg import solve_svrg_symmetric
from cola.utils.dispatch import parametric
from cola.utils import export
from cola.annotations import Unitary, PSD
from cola import SelfAdjoint


@parametric
class IterativeInverse(LinearOperator):
    def __str__(self):
        return f"{str(self.A)}⁻¹"


class CholeskyInverse(LinearOperator):
    def __init__(self, A, **kwargs):
        super().__init__(A.dtype, A.shape)
        self.ops = A.ops
        self.L = self.ops.cholesky(A.to_dense())
        self.info = {}

    def _matmat(self, X):
        Y = self.ops.solvetri(self.L, X, lower=True)
        soln = self.ops.solvetri(self.L.T, Y, lower=False)
        return soln


class LUInverse(LinearOperator):
    def __init__(self, A, **kwargs):
        super().__init__(A.dtype, A.shape)
        self.ops = A.ops
        self.A = A.to_dense()
        self.info = {}

    def _matmat(self, X):
        # TODO: see whether to call LU function from lax directly
        soln = self.ops.lu_solve(self.A, X)
        return soln


class CGInverse(IterativeInverse):
    def __init__(self, A, **kwargs):
        super().__init__(A.dtype, A.shape)
        self.A = A
        self.kwargs = kwargs
        self.info = {}

    def _matmat(self, X):
        out, self.info = cg(self.A, X, **self.kwargs)
        return out


class GMResInverse(IterativeInverse):
    def __init__(self, A, **kwargs):
        super().__init__(A.dtype, A.shape)
        self.A = A
        self.kwargs = kwargs
        self.info = {}

    def _matmat(self, X):
        out, self.info = gmres(self.A, X, **self.kwargs)
        return out


class SymmetricSVRGInverse(IterativeInverse):
    def __init__(self, A, **kwargs):
        super().__init__(A.dtype, A.shape)
        self.A = A
        self.kwargs = kwargs
        self.info = {}

    def _matmat(self, X):
        out, self.info = solve_svrg_symmetric(self.A, X, **self.kwargs)
        return out


class GenericSVRGInverse(IterativeInverse):
    pass


@dispatch
@export
def inverse(A: LinearOperator, **kwargs):
    """(lazily) computes the inverse of a linear operator, equivalent to solve.

    Args:
        A (LinearOperator): The linear operator to compute the inverse of.
        tol (float, optional): The tolerance criteria. Defaults to 1e-6.
        P (array, optional): Preconditioner matrix
        x0 (array, optional): The initial guess for the solution
        pbar (bool, optional): Whether to show a progress bar. Defaults to False.
        max_iters (int, optional): The maximum number of iterations. Defaults to 5000.
        method (str, optional): Method to use, defaults to 'auto',
         options are 'auto', 'dense', 'krylov', 'svrg'.

    Returns:
        Array: The inverse of the linear operator.

    Example:
        >>> A = MyLinearOperator()
        >>> x = cola.inverse(A) @ b

    """
    kws = dict(method="auto", tol=1e-6, P=None, x0=None, pbar=False, max_iters=5000)
    assert not kwargs.keys() - kws.keys(), f"Unknown kwargs {kwargs.keys()-kws.keys()}"
    kws.update(kwargs)
    method = kws.pop('method', 'auto')
    if method == 'dense' or (method == 'auto' and np.prod(A.shape) <= 1e6):
        # return lazify(A.ops.inv(A.to_dense()))
        if A.isa(PSD):
            return CholeskyInverse(A)
        else:
            return LUInverse(A)
    # elif issubclass(type(A), SelfAdjoint[Sum]) and (method == 'svrg' or (method == 'auto' and len(A.A.Ms) > 1e4)):
    #     return SymmetricSVRGInverse(A.A, **kws)
    elif issubclass(type(A), Sum) and (method == 'svrg' or (method == 'auto' and len(A.Ms) > 1e4)):
        return GenericSVRGInverse(A, **kws)
    elif A.isa(SelfAdjoint) and ((method == 'cg' or method == 'krylov') or (method == 'auto' and np.prod(A.shape) > 1e6)):
        return CGInverse(A, **kws)
    elif (method == 'gmres' or method == 'krylov') or (method == 'auto' and np.prod(A.shape) > 1e6):
        return GMResInverse(A, **kws)
    else:
        raise ValueError(f"Unknown method {method} or CoLA didn't fit any selection criteria")


@dispatch
def inverse(A: Identity, **kwargs):
    return A


@dispatch
def inverse(A: ScalarMul, **kwargs):
    return ScalarMul(1 / A.c, shape=A.shape, dtype=A.dtype)

@dispatch
def inverse(A: Permutation, **kwargs):
    return Permutation(A.ops.argsort(A.perm),A.dtype)

@dispatch(cond = lambda A, **kwargs: all([M.shape[-2] == M.shape[-1] for M in A.Ms]))
def inverse(A: Product, **kwargs) -> Product:
    output = reversed([inverse(M, **kwargs) for M in A.Ms])
    return Product(*output)


@dispatch
def inverse(A: BlockDiag, **kwargs):
    return BlockDiag(*[inverse(M, **kwargs) for M in A.Ms], multiplicities=A.multiplicities)


@dispatch
def inverse(A: Kronecker, **kwargs):
    return Kronecker(*[inverse(M, **kwargs) for M in A.Ms])


@dispatch
def inverse(A: Diagonal, **kwargs):
    return Diagonal(1. / A.diag)


# @dispatch(cond = lambda A, **kwargs: A.isa(Unitary), precedence=1)
# def inverse(A: LinearOperator, **kwargs):
#     return Unitary(A.H)
