import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
import multipledispatch


def sparse(*args, **kwargs):
    return sp.csc_matrix(*args, **kwargs)


@multipledispatch.dispatch(sp.spmatrix, sp.spmatrix)
def relative_error(mat_ref, mat, ord='fro'):
    if ord == 'fro':
        ord = 2
    temp = mat_ref - mat
    num = np.linalg.norm(sp.find(temp)[2], ord=ord)
    denom = np.linalg.norm(sp.find(mat_ref)[2], ord=ord)
    return num / denom


@multipledispatch.dispatch(np.ndarray, np.ndarray)
def relative_error(mat_ref, mat, ord='fro'):
    if ord == 0:
        def reshape(arr):
            return arr.flatten()
    else:
        def reshape(arr):
            return arr
    mat_ref_flat = reshape(mat_ref)
    num = np.linalg.norm(mat_ref_flat - reshape(mat), ord=ord)
    denom = np.linalg.norm(mat_ref_flat, ord=ord)
    return num / denom


def normalized_error(mat1, mat2, ord='fro'):
    if sp.issparse(mat1) and sp.issparse(mat2):
        if ord == 'fro':
            ord = 2
        norm1 = np.linalg.norm(mat1.data, ord=ord)
        norm2 = np.linalg.norm(mat2.data, ord=ord)
        diff = (mat1 / norm1) - (mat2 / norm2)
        res = np.linalg.norm(diff.data, ord=ord)
    else:
        if ord == 0:
            def reshape(arr):
                return arr.flatten()
        else:
            def reshape(arr):
                return arr
        norm1 = np.linalg.norm(mat1, ord=ord)
        norm2 = np.linalg.norm(mat2, ord=ord)
        diff = (mat1 / norm1) - (mat2 / norm2)
        res = np.linalg.norm(diff, ord=ord)
    return res


@multipledispatch.dispatch(np.ndarray)
def count_nonzero(array):
    return np.count_nonzero(array)


@multipledispatch.dispatch(sp.spmatrix)
def count_nonzero(array):
    return array.nnz


@multipledispatch.dispatch(np.ndarray)
def frobenius_norm(array):
    return np.linalg.norm(array)


@multipledispatch.dispatch(sp.spmatrix)
def frobenius_norm(array):
    return np.sqrt(array.multiply(array).sum())


def svds(array, k):
    success = False
    tol = 0
    while not success:
        if tol > 1e-3:
            raise spla.ArpackNoConvergence('SVD failed to converge with '
                                           'tol={0}'.format(tol))
        try:
            u, s, vt = spla.svds(array, k, tol=tol)
            success = True
        except spla.ArpackNoConvergence:
            if tol == 0:
                tol = 1e-10
            else:
                tol *= 10
    return u, s, vt


class UpdatableSVD:
    def __init__(self, array):
        self.shape = array.shape
        self.u, self.s, self.vt = np.linalg.svd(array, full_matrices=False)

    def update(self, a, b):
        if self.s is None:
            return

        m = self.u.T.dot(a)
        p = a - self.u.dot(m)
        r_a = frobenius_norm(p)
        p /= r_a

        n = self.vt.dot(b)
        q = b - self.vt.T.dot(n)
        r_b = frobenius_norm(q)
        q /= r_b

        u_a = np.append(m, [r_a])
        v_b = np.append(n, [r_b])

        k = np.diag(np.append(self.s, [0]))
        k += np.outer(u_a, v_b)

        self._inner_update(p, q, k)

    def remove_column(self, idx):
        if self.s is None:
            return

        p = np.zeros((self.u.shape[0], 1))

        b = np.zeros((self.shape[1],))
        b[idx] = 1
        n = self.vt[:, idx]
        q = b - self.vt.T.dot(n)
        r_b = frobenius_norm(q)
        q = np.atleast_2d(q) / r_b

        u_a = np.append(n, [0])
        v_b = np.append(n, [r_b])

        k = np.dot(np.diag(np.append(self.s, [0])),
                   np.identity(self.s.size + 1) - np.outer(u_a, v_b))
        self._inner_update(p, q, k)

    def _inner_update(self, p, q, k):
        try:
            inner_u, s_new, inner_vt = np.linalg.svd(k)
        except np.linalg.LinAlgError:
            self.u = None
            self.s = None
            self.vt = None
            return

        if s_new.size > self.s.size:
            if len(p.shape) == 1:
                p = np.atleast_2d(p).T
            self.u = np.hstack((self.u, p))
            self.vt = np.vstack((self.vt, q))
        # update and crop
        self.u = np.dot(self.u, inner_u)
        self.s = s_new
        self.vt = np.dot(inner_vt, self.vt)
        self.trim()

    def trim(self):
        orig_size = min(self.shape)
        self.u = self.u[:, :orig_size]
        self.s = self.s[:orig_size]
        self.vt = self.vt[:orig_size, :]
