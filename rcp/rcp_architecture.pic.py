def draw(d):
    d.Socket = d.box(wid=d['boxht'] * 2, ht=d['boxht'])("UDP Socket")

    d.move(to=d.Socket.w)
    d.line(left=d['boxht'])("packets")("below")
    d.arrow(up=d['boxht'])
    d.ReadLoop = d.box(dashed="", wid=d['boxht'] * 2, ht=d['boxht'] * 2)("Read Loop")

    d.move(to=d.Socket.e)
    d.move(right=d['boxht'])
    with d.nested():
        d.arrow(left=d['boxht'])("packets")("below")
    d.line(up=d['boxht'])
    d.WriteLoop = d.box(dashed="", wid=d['boxht'] * 2, ht=d['boxht'] * 2)("Write Loop")

    d.move(to=d.WriteLoop.n).then(up=d['boxht'] * 1.5)
    with d.nested():
        d.arrow(down=d['boxht'] * 1.5)("Packets to Send")("ljust")
    d.StreamDisassembler = d.box(wid=d['boxht'] * 2, ht=d['boxht'])
    d.move(to=d.StreamDisassembler.c)
    with d.nested():
        d['']("")("Stream")("above")
        d['']("")("Disassembler")("below")

    d.move(to=d.ReadLoop.n)
    d.arrow(up=d['boxht'] * 1.5)("Filtered Packets")("rjust")
    d.PacketAssembler = d.box(wid=d['boxht'] * 2, ht=d['boxht'])
    d.move(to=d.PacketAssembler.c)
    with d.nested():
        d['']("")("Packet")("above")
        d['']("")("Assembler")("below")

    d.move(to=d.PacketAssembler.n)
    d.arrow(up=d['boxht']).then(right=d['boxht'])("stream")("above")
    d.RCPSocket = d.box(wid=d['boxht'] * 2, ht=d['boxht'])("RCP Socket")
    d.arrow(right=d['boxht']).then(down=d['boxht'])("stream")("ljust")

    d.move(to=d.RCPSocket.n).then(left=d['boxht'] * .2)
    d.arrow(up=d['boxht'] * .5)("stream")("rjust")
    d.move(to=d.RCPSocket.n).then(up=d['boxht'] * .5)
    d['']("")("Application")("above")
    d.move(to=d.RCPSocket.n).then(right=d['boxht'] * .2).then(up=d['boxht'] * .5)
    d.arrow(down=d['boxht'] * .5)("stream")("ljust")

    d.move(to=d.ReadLoop.w).then(right=d['boxht'] * .1).then(up=d['boxht'] * .3)
    d.arc(to=d.ReadLoop.w + (d['boxht'] * .1, 0), cw="").with_(c=d.ReadLoop.c)
    d.arrow(up=.1)

    d.move(to=d.WriteLoop.w).then(right=d['boxht'] * .1).then(up=d['boxht'] * .3)
    d.arc(to=d.WriteLoop.w + (d['boxht'] * .1, 0), cw="").with_(c=d.WriteLoop.c)
    d.arrow(up=.1)

    d.move(to=(d.Socket.c, d.ReadLoop.c))
    d.box(ht=d['boxht'] * 2.7, wid=d['boxht'] * 8).with_(c=d.Here)("RCP Router")
