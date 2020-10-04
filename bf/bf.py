from nmigen import *
from enum import Enum, unique
from nmigen.cli import main
from nmigen.back.pysim import Simulator, Delay, Settle

@unique
class Op(Enum):
    NOP = 0
    MOVE = 1
    UPDATE = 2
    LOOP = 3
    OUT = 4

class Decoder(Elaboratable):
    def __init__(self):
        self.input = Signal(7)
        self.op = Signal(Op)
        self.neg = Signal()
    
    def elaborate(self, platform):
        m = Module()
        m.d.comb += self.neg.eq(Const(0))
        with m.Switch(self.input):
            with m.Case(ord(">")):
                m.d.comb += self.op.eq(Op.MOVE)
            with m.Case(ord("<")):
                m.d.comb += self.op.eq(Op.MOVE)
                m.d.comb += self.neg.eq(1)
            with m.Case(ord("+")):
                m.d.comb += self.op.eq(Op.UPDATE)
            with m.Case(ord("-")):
                m.d.comb += self.op.eq(Op.UPDATE)
                m.d.comb += self.neg.eq(1)
            with m.Case(ord("]")):
                m.d.comb += self.op.eq(Op.LOOP)
            with m.Case(ord("[")):
                m.d.comb += self.op.eq(Op.LOOP)
                m.d.comb += self.neg.eq(1)
            with m.Case(ord(".")):
                m.d.comb += self.op.eq(Op.OUT)
            with m.Default():
                m.d.comb += self.op.eq(Op.NOP)
        return m
    
    def ports(self):
        return [self.input, self.op, self.neg]

class Code(Elaboratable):
    def __init__(self, addr_bits, code):
        self.addr = Signal(addr_bits)
        self.rd = Signal(8)
        self.mem = Memory(width=8, depth=1<<addr_bits, init=code)

    def elaborate(self, platform):
        m = Module()
        m.submodules.rdport = rdport = self.mem.read_port()
        m.d.comb += [
            rdport.addr.eq(self.addr),
            self.rd.eq(rdport.data),
        ]
        return m

class Tape(Elaboratable):
    def __init__(self, addr_bits):
        self.addr = Signal(addr_bits)
        self.rd = Signal(8)
        self.wr = Signal(8)
        self.we = Signal()
        self.mem = Memory(width=8, depth=1<<addr_bits)

    def elaborate(self, platform):
        m = Module()
        m.submodules.rdport = rdport = self.mem.read_port()
        m.submodules.wrport = wrport = self.mem.write_port()
        m.d.comb += [
            rdport.addr.eq(self.addr),
            wrport.addr.eq(self.addr),
            self.rd.eq(rdport.data),
            wrport.data.eq(self.wr),
            wrport.en.eq(self.we),
        ]
        return m

class Cpu(Elaboratable):
    def __init__(self, code_bits, tape_bits, code):
        self.pc = Signal(code_bits)
        self.ptr = Signal(tape_bits)
        self.ptr_next = Signal(tape_bits)
        self.code = Code(code_bits, code)
        self.tape = Tape(tape_bits)
        self.decoder = Decoder()
        self.op = Signal(Op)
        self.neg = Signal()
        self.pc_next = Signal(code_bits)
        self.pc_skip = Signal()
        self.pc_neg = Signal()
        self.pc_neg_next = Signal()
        self.vl = Signal(8)
        self.vl_zero = Signal()
        self.skip_level = Signal(8)
        self.skip_level_next = Signal(8)
        self.out = Signal(8)
        self.out_en = Signal()

    def elaborate(self, platform):
        m = Module()
        m.submodules.code = self.code
        m.submodules.tape = self.tape
        m.submodules.decoder = self.decoder

        m.d.comb += [
            self.decoder.input.eq(self.code.rd[0:7]),
            self.code.addr.eq(self.pc_next),
            self.tape.addr.eq(self.ptr_next),
            self.op.eq(self.decoder.op),
            self.neg.eq(self.decoder.neg),
            self.vl.eq(self.tape.rd),
            self.vl_zero.eq(self.vl == 0),
            self.pc_neg_next.eq(self.pc_neg),
            self.pc_next.eq(self.pc + Mux(self.pc_neg_next, -1, 1)),
            self.ptr_next.eq(self.ptr),
        ]

        m.d.sync += [
            self.pc.eq(self.pc_next),
            self.pc_neg.eq(self.pc_neg_next),
            self.ptr.eq(self.ptr_next),
            self.out_en.eq(0),
        ]

        with m.If(self.pc_skip):
            with m.If(self.op == Op.LOOP):
                m.d.comb += [
                    self.skip_level_next.eq(self.skip_level + Mux(self.neg, -1, +1))
                ]
                m.d.sync += [
                    self.skip_level.eq(self.skip_level_next)
                ]
                with m.If(self.skip_level_next == 0):
                    m.d.comb += [
                        self.pc_neg_next.eq(0),
                    ]
                    m.d.sync += [
                        self.pc_skip.eq(0),
                    ]
        with m.Else():
            with m.If(self.op == Op.MOVE):
                add = self.ptr + Mux(self.neg, -1, 1)
                m.d.comb += [
                    self.ptr_next.eq(add),
                ]

            with m.If(self.op == Op.UPDATE):
                add = self.vl + Mux(self.neg, -1, 1)
                m.d.comb += [
                    self.tape.wr.eq(add),
                    self.tape.we.eq(1),
                ]

            with m.If(self.op == Op.LOOP):
                with m.If(self.vl_zero == self.neg):
                    m.d.comb += [
                        self.pc_neg_next.eq(~self.neg),
                    ]
                    m.d.sync += [
                        self.pc_skip.eq(1),
                        self.skip_level.eq(Mux(self.neg, -1, 1)),
                    ]

            with m.If(self.op == Op.OUT):
                m.d.sync += [
                    self.out.eq(self.vl),
                    self.out_en.eq(1),
                ]

        return m

def assemble(source):
    return [0,0] + [ord(c) for c in source if c in "+-<>[],."]
