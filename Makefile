.PHONY: nbd
nbd:
	docker build -t lambdascheme/nbd nbd

.PHONY: nbd
nbd-push:
	docker push lambdascheme/nbd
