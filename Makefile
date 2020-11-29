.PHONY: nbd
nbd:
	docker build -f nbd/Dockerfile -t lambdascheme/nbd .

.PHONY: nbd
nbd-push:
	docker push lambdascheme/nbd
