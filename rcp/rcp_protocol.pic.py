def draw(d):
    # type -> 1 byte
    # seq number -> 4 bytes
    # acks -> 4 bytes
    # data -> up to 256 bytes

    d['']("")("Byte Offset")("rjust")

    with d.nested():
        d.move(right=d['boxwid'] * 4.4)
        d['']("")("RCP Packet")("ljust")

    with d.nested():
        for offset in [0, 1, 5, 9]:
            d.move(down=d['boxht'])
            d['']("")(str(offset))("rjust")

    d.move(down=d['boxht'])
    with d.nested():
        d.move(right=d['boxwid'] * .2)
        d.Type = d.box()
        d.move(to=d.Type.c)
        d['']("")("TYPE")("above")
        d.move(to=d.Type.c)
        d['']("")("(1 byte)")("below")

    d.move(down=d['boxht'])
    with d.nested():
        d.move(right=d['boxwid'] * .2)
        d.SN = d.box(wid=d['boxwid'] * 4)
        d.move(to=d.SN.c)
        d['']("")("SEQUENCE NUMBER")("above")
        d.move(to=d.SN.c)
        d['']("")("(4 bytes)")("below")

    d.move(down=d['boxht'])
    with d.nested():
        d.move(right=d['boxwid'] * .2)
        d.ACKS = d.box(wid=d['boxwid'] * 4)
        d.move(to=d.ACKS.c)
        d['']("")("ACKS")("above")
        d.move(to=d.ACKS.c)
        d['']("")("(4 bytes)")("below")

    d.move(down=d['boxht'] * 1.5)
    with d.nested():
        d.move(right=d['boxwid'] * .2)
        d.Data = d.box(wid=d['boxwid'] * 4, ht=d['boxht'] * 2)
        d.move(to=d.Data.c)
        d['']("")("DATA")("above")
        d.move(to=d.Data.c)
        d['']("")("(up to 256 bytes)")("below")
