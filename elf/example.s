# example.s

.text

func1:
	ret

.global func2
func2:
	call func1
	ret
