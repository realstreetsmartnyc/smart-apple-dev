CC = clang
CFLAGS = -target arm64-apple-ios15.0 -isysroot $(shell smart-apple-dev sdk path iphoneos) -O0 -g
LDFLAGS = -framework Foundation -framework UIKit
TARGET = {{NAME}}
SOURCES = main.m

all: $(TARGET)

$(TARGET): $(SOURCES)
	$(CC) $(CFLAGS) -o $(TARGET) $(SOURCES) $(LDFLAGS)

clean:
	rm -f $(TARGET)
