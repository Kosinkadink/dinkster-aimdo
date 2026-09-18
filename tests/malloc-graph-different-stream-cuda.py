import dinkster_aimdo.control as aimdo
import torch


M = 1024 * 1024

assert aimdo.init("cuda")
assert aimdo.init_device(torch.cuda.current_device())
torch.empty(1, device="cuda")

graph = aimdo.record(torch.cuda.current_stream())
value = torch.empty(8 * M, dtype=torch.uint8, device="cuda")
pointer = value.data_ptr()
del value
assert not graph.pop()

other = torch.cuda.Stream()
with torch.cuda.stream(other):
    graph.push()
    with graph.use_stream(other):
        value = torch.empty(8 * M, dtype=torch.uint8, device="cuda")
        assert value.data_ptr() == pointer
        del value
    assert not graph.pop()
other.synchronize()

print("Different-stream replay branch test passed")
