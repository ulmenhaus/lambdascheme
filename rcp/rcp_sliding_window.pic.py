def draw(d):
    d['boxht'] = d['boxht'] / 3
    d['boxwid'] = d['boxht']

    d['']("")("Iteration 1")("rjust")
    d.right()
    with d.nested():
        for i in range(20):
            d.box()
    with d.nested():
        d.move(up=d['boxht'] / 2)
        d.line(up=d['boxht'])
        d['']("")("Packet 0")("above")
    with d.nested():
        d.move(right=d['boxwid'] * 16).then(up=d['boxht'] / 2)
        d.line(up=d['boxht'])
        d['']("")("Packet 15")("above")
    d.move(down=d['boxht'] / 2)
    d.line(down=d['boxht']).then(right=d['boxwid'])
    d.move(right=d['boxwid'] * 14)("Sliding window (16 packets)")
    d.line(right=d['boxwid']).then(up=d['boxht'])

    d.move(down=d['boxht'] * 3)
    d.arrow(right=d['boxwid'] * 14)("Send Packets 0 through 15")("above")
    d.move(down=d['boxht'] * 3)
    d.arrow(left=d['boxwid'] * 14)("Receive ACK of Packet 2")("above")

    d.move(down=d['boxwid'] * 5).then(left=d['boxwid'] * 16).then(right=0)
    d['']("")("Iteration 2")("rjust")
    with d.nested():
        for i in range(3):
            d.box(filled="")
        for i in range(17):
            d.box()
    with d.nested():
        d.move(up=d['boxht'] / 2)
        d.line(up=d['boxht'])
        d['']("")("Packet 0")("above")
    with d.nested():
        d.move(right=d['boxwid'] * 16).then(up=d['boxht'] / 2)
        d.line(up=d['boxht'])
        d['']("")("Packet 15")("above")
    d.move(down=d['boxht'] / 2).then(right=d['boxwid'] * 3)
    d.line(down=d['boxht']).then(right=d['boxwid'])
    d.move(right=d['boxwid'] * 14)("Sliding window (16 packets)")
    d.line(right=d['boxwid']).then(up=d['boxht'])

    d.move(down=d['boxht'] * 3).then(left=d['boxwid'] * 3)
    d.arrow(right=d['boxwid'] * 14)("Send Packets 3 through 18")("above")
