# hello_bootable.s

.code16
.global boot
boot: 
	mov $0xe, %ah
	mov $msg, %si

print_si:
	lodsb
	int $0x10
	cmp $0, %al
	jne print_si

halt:
	hlt

msg:
	.ascii "Hello world!" 
	len = . - msg

.fill 510-(.-boot), 1, 0
.word 0xaa55
