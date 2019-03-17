import chainer
import numpy as np


def _flatten(x):
    if isinstance(x, chainer.Variable):
        x = x.data
    x = chainer.backends.cuda.to_cpu(x)
    return x.flatten()


def convert_sparse_with_edge_type(data, row, col, num_nodes,
                                  edge_type, num_edge_type):
    """Convert a sparse matrix with edge type to a regular COO matrix.

    Args:
        data (numpy.ndarray): the entries of the batched sparse matrix.
        row (numpy.ndarray): the row indices of the matrix entries.
        col (numpy.ndarray): the column indices of the matrix entries.
        num_nodes (int): the number of nodes in the batched graph.
        edge_type (numpy.ndarray): edge type information of edges.
        num_edge_type (int): number of edge type.

    Returns (chainer.utils.CooMatrix): new sparse COO matrix whose minibatch
        size is equal to ((original minibatch size) * num_edge_type).
    """
    assert len(data.shape) == 2
    assert row.shape == data.shape
    assert col.shape == data.shape
    assert edge_type.shape == data.shape

    mb, length = data.shape

    data = _flatten(data)
    row = _flatten(row)
    col = _flatten(col)
    edge_type = _flatten(edge_type)

    # From now on, suppose that
    # edge_type = [[1, 1, 3, 1], [0, 2, 1, 0]] as example.
    # Then,
    # pos_mb    = [1, 1, 3, 1, 4, 6, 5, 4].
    pos_mb = np.repeat(np.arange(mb), length) * num_edge_type + edge_type

    # argsort    = [0, 1, 3, 2, 4, 7, 6, 5]
    # sorted_pos = [1, 1, 1, 3, 4, 4, 5, 6]
    argsort = pos_mb.argsort()
    sorted_pos = pos_mb[argsort]

    # df         = [0, 0, 0, 1, 1, 0, 1, 1]
    df = np.diff(sorted_pos, prepend=sorted_pos[0]) != 0
    # extract    = [3, 4, 6, 7]
    extract = np.arange(mb * length)[df]
    # d_extract  = [3, 1, 2, 1]
    d_extract = np.diff(extract, prepend=0)

    # p          = [0, 0, 0, 3, 1, 0, 2, 1]
    p = np.zeros(mb * length, dtype=np.int32)
    p[df] = d_extract
    # pos_i_perm = [0, 1, 2, 0, 0, 1, 0, 0]
    pos_i_perm = np.arange(mb * length) - p.cumsum()
    # pos_i      = [0, 1, 0, 2, 0, 0, 0, 1]
    pos_i = np.zeros_like(pos_i_perm)
    pos_i[argsort] = pos_i_perm

    # new_length = 3
    new_length = pos_i.max() + 1
    new_mb = mb * num_edge_type

    new_data = np.zeros((new_mb, new_length), dtype=data.dtype)
    new_data[pos_mb, pos_i] = data

    new_row = np.zeros((new_mb, new_length), dtype=np.int32)
    new_row[pos_mb, pos_i] = row

    new_col = np.zeros((new_mb, new_length), dtype=np.int32)
    new_col[pos_mb, pos_i] = col

    new_shape = (num_nodes, num_nodes)
    return chainer.utils.CooMatrix(new_data, new_row, new_col, new_shape)
