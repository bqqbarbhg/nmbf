import bf
from nmigen import *
from nmigen_boards.tinyfpga_bx import TinyFPGABXPlatform
from nmigen.build import Platform, Resource, Pins, Clock, Attrs, Connector

class SevenSegment(Elaboratable):
    def __init__(self):
        #  A
        # F B
        #  G
        # E C
        #  D
        A,B,C,D,E,F,G = 1,64,32,16,8,2,4
        FONT = [
            A|B|C|D|E|F,
            B|C,
            A|B|G|E|D,
            A|B|G|C|D,
            F|G|B|C,
            A|F|G|C|D,
            A|F|E|D|C|G,
            A|B|C,
            A|B|C|D|E|F|G,
            A|F|G|B|C,
            E|F|A|B|C|G,
            F|E|D|C|G,
            A|F|E|D,
            B|G|E|D|C,
            A|F|G|E|D,
            A|F|G|E,
        ]

        self.mem = Memory(width=8, depth=16, init=[~x for x in FONT])

        self.i = Signal(4)
        self.o = Signal(7)

    def elaborate(self, platform):
        m = Module()
        m.submodules.rdport = rdport = self.mem.read_port()
        m.d.comb += [
            rdport.addr.eq(self.i),
            self.o.eq(rdport.data[0:7]),
        ]
        return m

class BFTop(Elaboratable):

    def __init__(self, src):
        self.cpu = bf.Cpu(8, 8, bf.assemble(src))

    def elaborate(self, platform):
        m = Module()

        m.submodules.cpu = self.cpu
        m.submodules.seg = seg = SevenSegment()

        pins = Cat(platform.request("pin{}".format(n + 1)) for n in range(7))

        m.d.comb += [
            seg.i.eq(self.cpu.out[0:4]),
            pins.eq(seg.o),
        ]

        return m

src = """
[ Initial comment that is always skipped
Memory layout:
    0    start:    Always 1 for infinite loop
    1-3  counter:  Used to count 10*256*256 for delay
    4    num:      Current 7-segment number
]

+[ infinite loop

> move from start to counter
++++++++++[- do 10x
    >-[>-[-]<-]< Count 256 times to 256 (64k)
]

>>> move from counter to num
+ increment num
. display num
<<< move from num to counter
< move from counter to start

] loop back to start
"""

class Platform(TinyFPGABXPlatform):
    device = TinyFPGABXPlatform.device
    package = TinyFPGABXPlatform.package
    default_clk = TinyFPGABXPlatform.default_clk
    default_rst = TinyFPGABXPlatform.default_rst
    connectors = TinyFPGABXPlatform.connectors
    resources = TinyFPGABXPlatform.resources + [
        Resource("pin1", 0, Pins("A2", dir="o"), Attrs(IO_STANDARD="SB_LVCMOS")),
        Resource("pin2", 0, Pins("A1", dir="o"), Attrs(IO_STANDARD="SB_LVCMOS")),
        Resource("pin3", 0, Pins("B1", dir="o"), Attrs(IO_STANDARD="SB_LVCMOS")),
        Resource("pin4", 0, Pins("C2", dir="o"), Attrs(IO_STANDARD="SB_LVCMOS")),
        Resource("pin5", 0, Pins("C1", dir="o"), Attrs(IO_STANDARD="SB_LVCMOS")),
        Resource("pin6", 0, Pins("D2", dir="o"), Attrs(IO_STANDARD="SB_LVCMOS")),
        Resource("pin7", 0, Pins("D1", dir="o"), Attrs(IO_STANDARD="SB_LVCMOS")),
        Resource("pin8", 0, Pins("E2", dir="o"), Attrs(IO_STANDARD="SB_LVCMOS")),
    ]

if __name__ == "__main__":
    bftop = BFTop(src)
    platform = Platform()
    platform.build(bftop, do_program=True)
