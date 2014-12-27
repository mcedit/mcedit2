UI_FILES := $(wildcard *.ui)
UI_OUTPUT:= $(addprefix py/ui_,$(UI_FILES:.ui=.py))

py/ui_%.py: %.ui
	pyside-uic $< -o $@

py_ui: $(UI_OUTPUT)

default: py_ui