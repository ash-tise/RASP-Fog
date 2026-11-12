"""
Unit tests for rasp_nsfnet.py. Run from the repository root:

    python3 tests/test_rasp_nsfnet.py        (or: python3 -m pytest tests)

Each test builds a tiny hand-made scenario on the NSFNET network so the expected
decision is known in advance.
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import rasp_nsfnet as nf


def req(rid, ingress, kind="sensor", t=0.0, end=1e9, c=None, deadline=None, sigma=None):
    r = {"id": rid, "kind": kind, "t": t, "ingress": ingress, "end": end}
    cls = nf.TYPES[kind]
    r.update(sigma=sigma or cls["sigma"], c=c or cls["c"], m=cls["m"], b=cls["b"],
             deadline=deadline or cls["deadline"][1])
    return r


def reset(threat=None):
    nf.THREAT = threat or nf.uniform_threat([(0, 1)])
    nf.TAU_H = 8
    nf.PROTECT = True


# ------------------------------------------------------------------ reservations
def test_path_and_node_reservation_and_release():
    reset()
    net = nf.Network()
    r = req(1, ingress=1)
    r.update(node=14, k=2)
    net.place(r)
    dc, dm, db = nf.demand(r, 2)
    path = net.routes[(1, 14)][1]
    assert len(path) >= 2
    for l in path:
        assert abs(net.link_used[l] - db) < 1e-9
    assert abs(net.node_used[14][0] - dc) < 1e-9 and abs(net.node_used[14][2] - db) < 1e-9
    assert net.check() == []
    net.release(r)
    assert all(abs(v) < 1e-9 for v in net.link_used.values())
    assert all(abs(x) < 1e-9 for u in net.node_used.values() for x in u)


def test_queueing_uses_projected_utilization():
    reset()
    net = nf.Network()
    other = req(1, ingress=2, kind="industrial", c=50, deadline=1e6)
    other.update(node=2, k=1)
    net.place(other)
    cand = req(2, ingress=2, kind="industrial", c=20, deadline=1e6)
    c = nf.evaluate(cand, 2, 1, net)
    used = nf.demand(other, 1)[0]
    u = (used + nf.demand(cand, 1)[0]) / net.nodes[2]["cpu"]
    assert abs(c["chi"] - nf.CHI_MS * u / (1 - u)) < 1e-9
    # re-evaluating an active request removes its own old reservation first
    c_self = nf.evaluate(other, 2, 1, net)
    u_self = used / net.nodes[2]["cpu"]
    assert abs(c_self["chi"] - nf.CHI_MS * u_self / (1 - u_self)) < 1e-9


def test_incumbent_deadline_protected():
    reset()
    net = nf.Network()
    # incumbent with almost no slack: any queueing pushes it late
    inc = req(1, ingress=2, kind="sensor", deadline=None)
    inc.update(node=2, k=1)
    inc["deadline"] = nf.current_delay(inc, net, chi=0) + 0.01
    net.place(inc)
    big = req(2, ingress=2, kind="industrial", c=60, deadline=1e6)
    assert nf.evaluate(big, 2, 1, net) is None           # would make the incumbent late
    nf.PROTECT = False
    assert nf.evaluate(big, 2, 1, net) is not None
    nf.PROTECT = True


# ------------------------------------------------------------------ adaptation
def _upgrade_scenario(fill_cpu):
    """One sensor at node 2 with q1; threat rises to 2 at t=5. fill_cpu of node 2's
    CPU is taken by a filler that stays at q3."""
    reset(nf.uniform_threat([(0, 1), (5, 2)]))
    net = nf.Network()
    r = req(1, ingress=2, c=10, deadline=1e6)
    r.update(node=2, k=1, history=[(0, 1)])
    net.place(r)
    if fill_cpu:
        f = req(2, ingress=2, kind="industrial", sigma=3, deadline=1e6,
                c=fill_cpu / (1 + nf.PROFILES[3]["dc"]))
        f.update(node=2, k=3, history=[(0, 3)])
        net.place(f)
    return net, r


def test_local_first_upgrade():
    net, r = _upgrade_scenario(fill_cpu=0)
    log = []
    nf.adapt(r, 5, net, log, nf.POLICIES["RASP-Fog"])
    assert log[-1][1] == "UPGRADE" and r["node"] == 2 and r["k"] >= 2
    assert net.check() == []


def test_relocation_when_local_upgrade_does_not_fit():
    # node 2 has 100 CPU; sensor at q1 uses 10.5, at q2 11; filler leaves < 11
    cap = nf.SMALL["cpu"]
    net, r = _upgrade_scenario(fill_cpu=cap - 10.6)
    log = []
    nf.adapt(r, 5, net, log, nf.POLICIES["RASP-Fog"])
    assert log[-1][1] == "MOVE" and r["node"] != 2 and r["k"] >= 2
    assert r["relocations"][0]["from"] == 2
    assert net.check() == []


def test_profile_only_terminates_instead_of_moving():
    cap = nf.SMALL["cpu"]
    net, r = _upgrade_scenario(fill_cpu=cap - 10.6)
    log = []
    nf.adapt(r, 5, net, log, nf.POLICIES["RASP-Profile"])
    assert log[-1][1] == "TERMINATE" and r["id"] not in net.active_ids
    assert net.check() == []


def test_sa_ff_relocates_to_first_feasible_in_order():
    cap = nf.SMALL["cpu"]
    net, r = _upgrade_scenario(fill_cpu=cap - 10.6)
    log = []
    nf.adapt(r, 5, net, log, nf.POLICIES["SA-FF"])
    order = [n for n in net.ff_order[2] if n != 2]
    assert log[-1][1] == "MOVE" and r["node"] == order[0]


def test_sa_ff_order_is_hops_then_id():
    net = nf.Network()
    for s in nf.FOG:
        o = net.ff_order[s]
        assert o[0] == s and o[-1] == nf.CLOUD
        hops = [len(net.routes[(s, j)][1]) for j in o[:-1]]
        assert hops == sorted(hops)


def test_downgrade_waits_for_hysteresis():
    reset(nf.uniform_threat([(0, 2), (10, 1)]))
    for tau, first_down in ((0, 10), (8, 18)):
        nf.TAU_H = tau
        net = nf.Network()
        r = req(1, ingress=2, c=1, deadline=1e6)
        r.update(node=2, k=2, history=[])
        net.place(r)
        log, when = [], None
        for t in range(0, 30):
            nf.adapt(r, t, net, log, nf.POLICIES["RASP-Fog"])
            if when is None and log and log[-1][1] == "DOWNGRADE":
                when = t
        assert when == first_down, (tau, when)
    nf.TAU_H = 8


# ------------------------------------------------------------------ whole runs
def test_full_runs_never_under_protect_or_break_capacity():
    for policy in ("RASP-Fog", "RASP-Reloc", "RASP-Profile", "SA-FF", "Static-Strong"):
        nf.PROTECT = True
        nf.TAU_H = 8
        nf.THREAT = nf.random_threat(random.Random(7), 200, p_up=0.4)
        arr = nf.make_arrivals(random.Random(3), 30, 60)
        m = nf.simulate(policy, arr, 60, warmup=10, check=True)
        assert m["problems"] == [], (policy, m["problems"][:3])
        assert m["late"] == 0, policy
        assert m["under"] == 0, policy
        assert m["sla_miss"] == 0, policy               # PROTECT keeps incumbents on time
        # a terminated or under-protected request is never a secure completion
        assert m["secure"] + m["terminated"] + m["rejected"] <= m["arrivals"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(f"{len(tests)} tests passed")
