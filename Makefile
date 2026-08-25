# SPDX-License-Identifier: GPL-3.0-or-later
# SPDX-PackageHomePage: https://github.com/paxx12/screen-apps
# SPDX-FileCopyrightText: Copyright (c) 2026 @paxx12

APPS = fb-http
APPS_DIR = apps

.PHONY: all clean install uninstall $(APPS)

all: $(APPS)

$(APPS):
	$(MAKE) -C $(APPS_DIR)/$@

clean:
	@for app in $(APPS); do \
		$(MAKE) -C $(APPS_DIR)/$$app clean; \
	done

install:
	@for app in $(APPS); do \
		$(MAKE) -C $(APPS_DIR)/$$app install DESTDIR=$(DESTDIR); \
	done

uninstall:
	@for app in $(APPS); do \
		$(MAKE) -C $(APPS_DIR)/$$app uninstall DESTDIR=$(DESTDIR); \
	done
