TARGET = fb-http.py
SRC = fb-http.py
HTML_FILES = html/index.html

PREFIX ?= /usr/local
BINDIR ?= $(PREFIX)/bin
HTMLDIR ?= $(PREFIX)/share/fb-http/html

all:
	@echo "Nothing to build for $(TARGET)"

clean:
	@echo "Nothing to clean for $(TARGET)"

install: $(TARGET)
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 $(TARGET) $(DESTDIR)$(BINDIR)/$(TARGET)
	install -d $(DESTDIR)$(HTMLDIR)
	install -m 644 $(HTML_FILES) $(DESTDIR)$(HTMLDIR)/

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/$(TARGET)
	rm -rf $(DESTDIR)/usr/share/fb-http

.PHONY: all clean install uninstall
