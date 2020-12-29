# hello.s

.text

.global main
main:
	movl    $len,%edx
	movl    $msg,%ecx
	movl    $2,%ebx
	movl    $4,%eax
	int     $0x80

	movl    $0,%ebx
	movl    $1,%eax
	int     $0x80

.data

msg:
	.ascii    "Hello, world!\n"
	len = . - msg
