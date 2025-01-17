import torch
import numpy as np
from torch_sparse import SparseTensor
import torch_geometric
from torch_geometric.data import Data, HeteroData, Batch


def get_edge_index(num_src_nodes, num_dst_nodes, num_edges):
    row = torch.randint(num_src_nodes, (num_edges, ), dtype=torch.long)
    col = torch.randint(num_dst_nodes, (num_edges, ), dtype=torch.long)
    return torch.stack([row, col], dim=0)


def test_batch():
    torch_geometric.set_debug(True)

    x1 = torch.tensor([1, 2, 3], dtype=torch.float)
    e1 = torch.tensor([[0, 1, 1, 2], [1, 0, 2, 1]])
    adj1 = SparseTensor.from_edge_index(e1)
    s1 = '1'
    x2 = torch.tensor([1, 2], dtype=torch.float)
    e2 = torch.tensor([[0, 1], [1, 0]])
    adj2 = SparseTensor.from_edge_index(e2)
    s2 = '2'

    batch = Batch.from_data_list([
        Data(x=x1, edge_index=e1, adj=adj1, s=s1, num_nodes=3),
        Data(x=x2, edge_index=e2, adj=adj2, s=s2, num_nodes=2)
    ])

    assert str(batch) == ('Batch(x=[5], edge_index=[2, 6], adj=[5, 5, nnz=6], '
                          's=[2], num_nodes=5, batch=[5], ptr=[3])')
    assert len(batch) == 7
    assert batch.x.tolist() == [1, 2, 3, 1, 2]
    assert batch.edge_index.tolist() == [[0, 1, 1, 2, 3, 4],
                                         [1, 0, 2, 1, 4, 3]]
    edge_index = torch.stack(batch.adj.coo()[:2], dim=0)
    assert edge_index.tolist() == batch.edge_index.tolist()
    assert batch.s == ['1', '2']
    assert batch.num_nodes == 5
    assert batch.batch.tolist() == [0, 0, 0, 1, 1]
    assert batch.ptr.tolist() == [0, 3, 5]
    assert batch.num_graphs == 2

    data = batch[0]
    assert str(data) == ("Data(x=[3], edge_index=[2, 4], adj=[3, 3, nnz=4], "
                         "s='1', num_nodes=3)")
    data = batch[1]
    assert str(data) == ("Data(x=[2], edge_index=[2, 2], adj=[2, 2, nnz=2], "
                         "s='2', num_nodes=2)")

    assert len(batch.index_select([1, 0])) == 2
    assert len(batch.index_select(torch.tensor([1, 0]))) == 2
    assert len(batch.index_select(torch.tensor([True, False]))) == 1
    assert len(batch.index_select(np.array([1, 0], dtype=np.int64))) == 2
    assert len(batch.index_select(np.array([True, False]))) == 1
    assert len(batch[:2]) == 2

    data_list = batch.to_data_list()
    assert len(data_list) == 2
    assert len(data_list[0]) == 5
    assert data_list[0].x.tolist() == [1, 2, 3]
    assert data_list[0].edge_index.tolist() == [[0, 1, 1, 2], [1, 0, 2, 1]]
    edge_index = torch.stack(data_list[0].adj.coo()[:2], dim=0)
    assert edge_index.tolist() == data_list[0].edge_index.tolist()
    assert data_list[0].s == '1'
    assert data_list[0].num_nodes == 3

    assert len(data_list[1]) == 5
    assert data_list[1].x.tolist() == [1, 2]
    assert data_list[1].edge_index.tolist() == [[0, 1], [1, 0]]
    edge_index = torch.stack(data_list[1].adj.coo()[:2], dim=0)
    assert edge_index.tolist() == data_list[1].edge_index.tolist()
    assert data_list[1].s == '2'
    assert data_list[1].num_nodes == 2

    torch_geometric.set_debug(True)


def test_batching_with_new_dimension():
    torch_geometric.set_debug(True)

    class MyData(Data):
        def __cat_dim__(self, key, value, *args, **kwargs):
            if key == 'foo':
                return None
            else:
                return super().__cat_dim__(key, value, *args, **kwargs)

    x1 = torch.tensor([1, 2, 3], dtype=torch.float)
    foo1 = torch.randn(4)
    y1 = torch.tensor(1)

    x2 = torch.tensor([1, 2], dtype=torch.float)
    foo2 = torch.randn(4)
    y2 = torch.tensor(2)

    batch = Batch.from_data_list(
        [MyData(x=x1, foo=foo1, y=y1),
         MyData(x=x2, foo=foo2, y=y2)])

    assert batch.__repr__() == (
        'Batch(x=[5], y=[2], foo=[2, 4], batch=[5], ptr=[3])')
    assert len(batch) == 5
    assert batch.x.tolist() == [1, 2, 3, 1, 2]
    assert batch.foo.size() == (2, 4)
    assert batch.foo[0].tolist() == foo1.tolist()
    assert batch.foo[1].tolist() == foo2.tolist()
    assert batch.y.tolist() == [1, 2]
    assert batch.batch.tolist() == [0, 0, 0, 1, 1]
    assert batch.ptr.tolist() == [0, 3, 5]
    assert batch.num_graphs == 2

    data = batch[0]
    assert str(data) == ('MyData(x=[3], y=[1], foo=[4])')
    data = batch[1]
    assert str(data) == ('MyData(x=[2], y=[1], foo=[4])')

    torch_geometric.set_debug(True)


def test_recursive_batch():

    data1 = Data(
        x={
            '1': torch.randn(10, 32),
            '2': torch.randn(20, 48)
        }, edge_index=[get_edge_index(30, 30, 50),
                       get_edge_index(30, 30, 70)], num_nodes=30)

    data2 = Data(
        x={
            '1': torch.randn(20, 32),
            '2': torch.randn(40, 48)
        }, edge_index=[get_edge_index(60, 60, 80),
                       get_edge_index(60, 60, 90)], num_nodes=60)

    batch = Batch.from_data_list([data1, data2])

    assert len(batch) == 5
    assert batch.num_graphs == 2
    assert batch.num_nodes == 90

    assert torch.allclose(batch.x['1'],
                          torch.cat([data1.x['1'], data2.x['1']], dim=0))
    assert torch.allclose(batch.x['2'],
                          torch.cat([data1.x['2'], data2.x['2']], dim=0))
    assert (batch.edge_index[0].tolist() == torch.cat(
        [data1.edge_index[0], data2.edge_index[0] + 30], dim=1).tolist())
    assert (batch.edge_index[1].tolist() == torch.cat(
        [data1.edge_index[1], data2.edge_index[1] + 30], dim=1).tolist())
    assert batch.batch.size() == (90, )
    assert batch.ptr.size() == (3, )

    out1 = batch[0]
    assert len(out1) == 3
    assert out1.num_nodes == 30
    assert torch.allclose(out1.x['1'], data1.x['1'])
    assert torch.allclose(out1.x['2'], data1.x['2'])
    assert out1.edge_index[0].tolist(), data1.edge_index[0].tolist()
    assert out1.edge_index[1].tolist(), data1.edge_index[1].tolist()

    out2 = batch[1]
    assert len(out2) == 3
    assert out2.num_nodes == 60
    assert torch.allclose(out2.x['1'], data2.x['1'])
    assert torch.allclose(out2.x['2'], data2.x['2'])
    assert out2.edge_index[0].tolist(), data2.edge_index[0].tolist()
    assert out2.edge_index[1].tolist(), data2.edge_index[1].tolist()


def test_hetero_batch():
    e = ('p', 'a')
    data1 = HeteroData()
    data1['p'].x = torch.randn(100, 128)
    data1['a'].x = torch.randn(200, 128)
    data1[e].edge_index = get_edge_index(100, 200, 500)
    data1[e].edge_attr = torch.randn(500, 32)

    data2 = HeteroData()
    data2['p'].x = torch.randn(50, 128)
    data2['a'].x = torch.randn(100, 128)
    data2[e].edge_index = get_edge_index(50, 10, 300)
    data2[e].edge_attr = torch.randn(300, 32)

    batch = Batch.from_data_list([data1, data2])

    assert len(batch) == 5
    assert batch.num_graphs == 2
    assert batch.num_nodes == 450

    assert torch.allclose(batch['p'].x[:100], data1['p'].x)
    assert torch.allclose(batch['a'].x[:200], data1['a'].x)
    assert torch.allclose(batch['p'].x[100:], data2['p'].x)
    assert torch.allclose(batch['a'].x[200:], data2['a'].x)
    assert (batch[e].edge_index.tolist() == torch.cat([
        data1[e].edge_index, data2[e].edge_index + torch.tensor([[100], [200]])
    ], 1).tolist())
    assert torch.allclose(
        batch[e].edge_attr,
        torch.cat([data1[e].edge_attr, data2[e].edge_attr], 0))
    assert batch['p'].batch.size() == (150, )
    assert batch['p'].ptr.size() == (3, )
    assert batch['a'].batch.size() == (300, )
    assert batch['a'].ptr.size() == (3, )

    out1 = batch[0]
    assert len(out1) == 3
    assert out1.num_nodes == 300
    assert torch.allclose(out1['p'].x, data1['p'].x)
    assert torch.allclose(out1['a'].x, data1['a'].x)
    assert out1[e].edge_index.tolist() == data1[e].edge_index.tolist()
    assert torch.allclose(out1[e].edge_attr, data1[e].edge_attr)

    out2 = batch[1]
    assert len(out2) == 3
    assert out2.num_nodes == 150
    assert torch.allclose(out2['p'].x, data2['p'].x)
    assert torch.allclose(out2['a'].x, data2['a'].x)
    assert out2[e].edge_index.tolist() == data2[e].edge_index.tolist()
    assert torch.allclose(out2[e].edge_attr, data2[e].edge_attr)
