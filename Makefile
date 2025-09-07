IMAGE_NAME = sibuser/firefly-iii-tg-bot
VERSION = 0.0.4

.PHONY: all build push

all: build push

build:
	docker build -t $(IMAGE_NAME):$(VERSION) .

push:
	docker push $(IMAGE_NAME):$(VERSION)